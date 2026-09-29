"""Explicit backup and restore. No automatic deletion, no credential export."""
from __future__ import annotations

import json
from pathlib import Path

from .guardrails import ValidationError, canonical, digest
from .models import fields
from .runtime import _auth, _event
from .storage import initialize, transaction

TABLES = ("runs", "revisions", "questions", "reviews", "approvals", "exports", "events")


def backup(root: Path, token: str) -> dict:
    with transaction(root) as db:
        _auth(db, token, {"operator"})
        tables = {table: [dict(row) for row in db.execute("SELECT * FROM " + table)] for table in TABLES}
        bindings = [dict(r) for r in db.execute("SELECT id,actor,role FROM credentials")]
        data = {"schema_version": 1, "credential_bindings": bindings, "tables": tables}
        return {"data": data, "digest": digest(data)}


def restore(root: Path, envelope: dict, expected_digest: str) -> None:
    """Restore into a NEW private workspace; all prior keys/unused approvals revoked.

The digest must come from the operator's separately retained backup receipt.
Integrity hashes detect corruption, not malicious replacement with a new digest.
"""
    fields(envelope, {"data", "digest"}, "backup envelope")
    if len(canonical(envelope).encode()) > 20_000_000:
        raise ValidationError("Backup exceeds restore size limit")
    data = envelope["data"]
    fields(data, {"schema_version", "credential_bindings", "tables"}, "backup")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1 or envelope["digest"] != expected_digest or digest(data) != expected_digest:
        raise ValidationError("Backup digest or version mismatch")
    fields(data["tables"], set(TABLES), "backup tables")
    if not isinstance(data["credential_bindings"], list) or any(not isinstance(data["tables"][t], list) for t in TABLES):
        raise ValidationError("Invalid backup records")
    for table in ("revisions", "reviews", "exports"):
        for row in data["tables"][table]:
            if digest(json.loads(row["payload"])) != row["digest"]:
                raise ValidationError("Backup artifact digest mismatch")
    previous = {}
    for row in sorted(data["tables"]["events"], key=lambda e: e["sequence"]):
        value = {k: row[k] for k in ("run_id", "actor", "kind", "created", "previous_hash")}
        value["data"] = json.loads(row["data"])
        if row["previous_hash"] != previous.get(row["run_id"], "") or digest(value) != row["hash"]:
            raise ValidationError("Backup event chain mismatch")
        previous[row["run_id"]] = row["hash"]
    if root.exists():
        raise ValidationError("Restore destination must not exist")
    initialize(root)
    with transaction(root) as db:
        for binding in data["credential_bindings"]:
            fields(binding, {"id", "actor", "role"}, "credential binding")
            db.execute("INSERT INTO credentials(id,actor,role,hash,active) VALUES(?,?,?,'restored-disabled',0)", (binding["id"], binding["actor"], binding["role"]))
        for table in TABLES:
            columns = [c[1] for c in db.execute("PRAGMA table_info(" + table + ")")]
            for row in data["tables"][table]:
                fields(row, set(columns), "backup row")
                db.execute("INSERT INTO " + table + " (" + ",".join(columns) + ") VALUES(" + ",".join("?" for _ in columns) + ")", [row[c] for c in columns])
        db.execute("UPDATE approvals SET revoked=1 WHERE consumed=0")
        db.execute("UPDATE runs SET state='awaiting_approval',version=version+1 WHERE state='approved'")
        for run in db.execute("SELECT id FROM runs").fetchall():
            _event(db, run[0], "local-restore", "restored", {"backup_digest": expected_digest, "old_credentials_disabled": True})
