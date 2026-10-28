"""Explicit versioned backup/restore, including the additive refinement namespace.

No credentials, automatic deletion, or silent omission of supported run tables.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .guardrails import ValidationError, canonical, digest
from .storage import initialize, transaction
from .refine.contracts import fields, require
from .refine.identity import authenticate

TABLES = ("runs", "revisions", "questions", "reviews", "approvals", "exports", "events")
REFINE_TABLES = ("refine_meta", "refine_runs", "refine_records", "refine_exports")
MAX_BACKUP_BYTES = 20_000_000


def _legacy_event(db, run_id, receipt):
    previous = db.execute("SELECT hash FROM events WHERE run_id=? ORDER BY sequence DESC LIMIT 1", (run_id,)).fetchone()
    data = {"backup_digest": receipt, "old_credentials_disabled": True}
    body = {"run_id": run_id, "actor": "local-restore", "kind": "restored", "data": data,
            "created": time.time(), "previous_hash": previous[0] if previous else ""}
    db.execute("INSERT INTO events(run_id,actor,kind,data,created,previous_hash,hash) VALUES(?,?,?,?,?,?,?)",
               (run_id, body["actor"], body["kind"], canonical(data), body["created"], body["previous_hash"], digest(body)))


def backup(root: Path, token: str) -> dict:
    with transaction(root, write=False) as db:
        authenticate(db, token, {"operator"})
        tables = {table: [dict(row) for row in db.execute("SELECT * FROM " + table)] for table in TABLES}
        bindings = [dict(r) for r in db.execute("SELECT id,actor,role FROM credentials")]
        found = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'refine_%'")}
        require(not found or found == set(REFINE_TABLES), "Incomplete refinement namespace; backup cannot omit unknown tables")
        data = {"schema_version": 2 if found else 1, "credential_bindings": bindings, "tables": tables}
        if found:
            from .refine.controller import _schema
            _schema(db)
            data["refinement"] = {table: [dict(row) for row in db.execute("SELECT * FROM " + table)] for table in REFINE_TABLES}
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='workspace_meta'").fetchone():
            from .workspace import TABLES as WORKSPACE_TABLES
            require(bool(found), 'Workspace configuration requires the refinement namespace')
            data['schema_version'] = 3
            data['workspace'] = {table: [dict(row) for row in db.execute('SELECT * FROM ' + table)] for table in WORKSPACE_TABLES}
        require(len(canonical(data).encode()) <= MAX_BACKUP_BYTES, "Backup exceeds supported size; no partial backup was created")
        return {"data": data, "digest": digest(data)}


def _validate_refinement(tables):
    fields(tables, set(REFINE_TABLES), "refinement backup tables")
    require(all(isinstance(rows, list) for rows in tables.values()), "Invalid refinement records")
    require(tables["refine_meta"] == [{"version": 1}], "Unsupported refinement backup version")
    previous = {}
    for row in sorted(tables["refine_records"], key=lambda r: r["seq"]):
        require(digest(json.loads(row["payload"])) == row["digest"], "Refinement artifact digest mismatch")
        body = {key: row[key] for key in ("run_id", "kind", "actor", "credential_id", "digest", "previous_hash", "created")}
        require(row["previous_hash"] == previous.get(row["run_id"], "") and digest(body) == row["hash"], "Refinement event chain mismatch")
        previous[row["run_id"]] = row["hash"]
    for row in tables["refine_exports"]:
        require(digest(json.loads(row["payload"])) == row["digest"], "Refinement export digest mismatch")


def restore(root: Path, envelope: dict, expected_digest: str) -> None:
    """Restore into a NEW private workspace. Old keys are disabled, never copied.

The digest must be retained separately. Hashes detect corruption, not hostile
replacement of both the backup and receipt. Historical sealed exports survive.
"""
    fields(envelope, {"data", "digest"}, "backup envelope")
    require(len(canonical(envelope).encode()) <= MAX_BACKUP_BYTES + 256, "Backup exceeds restore size limit")
    data = envelope["data"]
    require(isinstance(data, dict), "Invalid backup data")
    version = data.get("schema_version")
    require(type(version) is int and version in {1, 2, 3}, "Unsupported backup version")
    fields(data, {"schema_version", "credential_bindings", "tables"} | ({"refinement"} if version >= 2 else set()) | ({"workspace"} if version == 3 else set()), "backup")
    require(envelope["digest"] == expected_digest and digest(data) == expected_digest, "Backup digest mismatch")
    fields(data["tables"], set(TABLES), "backup tables")
    require(isinstance(data["credential_bindings"], list) and all(isinstance(data["tables"][t], list) for t in TABLES), "Invalid backup records")
    for table in ("revisions", "reviews", "exports"):
        for row in data["tables"][table]:
            require(digest(json.loads(row["payload"])) == row["digest"], "Backup artifact digest mismatch")
    previous = {}
    for row in sorted(data["tables"]["events"], key=lambda e: e["sequence"]):
        body = {key: row[key] for key in ("run_id", "actor", "kind", "created", "previous_hash")}
        body["data"] = json.loads(row["data"])
        require(row["previous_hash"] == previous.get(row["run_id"], "") and digest(body) == row["hash"], "Backup event chain mismatch")
        previous[row["run_id"]] = row["hash"]
    if version >= 2:
        _validate_refinement(data["refinement"])
    if version == 3:
        from .workspace import TABLES as WORKSPACE_TABLES
        fields(data['workspace'], set(WORKSPACE_TABLES), 'workspace backup tables')
        require(data['workspace']['workspace_meta'] == [{'version': 1}], 'Unsupported workspace backup version')
        for row in data['workspace']['workspace_records']:
            require(digest(json.loads(row['payload'])) == row['digest'], 'Workspace configuration digest mismatch')
    require(not root.exists(), "Restore destination must not exist")
    initialize(root)
    if version >= 2:
        from .refine.controller import initialize as initialize_refinement
        initialize_refinement(root)
    if version == 3:
        from .workspace import initialize as initialize_settings
        initialize_settings(root)
    # A failed restore may leave an empty initialized workspace, never partially
    # committed evidence. Do not retry by overwriting it; inspect and choose anew.
    with transaction(root) as db:
        for binding in data["credential_bindings"]:
            fields(binding, {"id", "actor", "role"}, "credential binding")
            db.execute("INSERT INTO credentials(id,actor,role,hash,active) VALUES(?,?,?,'restored-disabled',0)", (binding["id"], binding["actor"], binding["role"]))
        selected = {table: data["tables"][table] for table in TABLES}
        if version >= 2:
            selected.update({table: data["refinement"][table] for table in REFINE_TABLES if table != 'refine_meta'})
        if version == 3:
            selected.update({table: data['workspace'][table] for table in WORKSPACE_TABLES if table != 'workspace_meta'})
        for table, rows in selected.items():
            columns = [c[1] for c in db.execute("PRAGMA table_info(" + table + ")")]
            for row in rows:
                fields(row, set(columns), "backup row")
                db.execute("INSERT INTO " + table + " (" + ",".join(columns) + ") VALUES(" + ",".join("?" for _ in columns) + ")", [row[c] for c in columns])
        if version == 3:
            db.execute("UPDATE workspace_jobs SET status='interrupted',message='Restored; inspect the requirement before explicitly retrying' WHERE status IN ('queued','running','applying','cancel_requested')")
        db.execute("UPDATE approvals SET revoked=1 WHERE consumed=0")
        db.execute("UPDATE runs SET state='awaiting_approval',version=version+1 WHERE state='approved'")
        for run in db.execute("SELECT id FROM runs").fetchall():
            _legacy_event(db, run[0], expected_digest)
        if version >= 2:
            from .refine.controller import _record
            db.execute("UPDATE refine_runs SET state='awaiting_review',version=version+1 WHERE state='approved'")
            who = {"actor": "local-restore", "id": "restored-disabled"}
            for run in db.execute("SELECT id FROM refine_runs").fetchall():
                _record(db, run[0], who, "restored", {"backup_digest": expected_digest, "old_credentials_disabled": True})
