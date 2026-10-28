"""Standalone, local-first workflow. Authenticated capabilities; no remote writes.

State and role keys must be held by a trusted operator, outside an agent sandbox.
This library cannot defend against its own OS owner rewriting the DB or code.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
from pathlib import Path
from typing import Any

from . import lint
from .guardrails import ValidationError, canonical, digest, identifier, open_questions, readiness
from .models import assessment, document, text
from .storage import transaction, write_private

POLICY_VERSION = "standalone-1"
ROLES = frozenset({"author", "reviewer", "operator"})
TERMINAL = frozenset({"exported", "rejected"})


def policy_digest() -> str:
    root = Path(__file__).resolve().parent
    paths = [root / name for name in ("runtime.py", "guardrails.py", "models.py", "lint.py")]
    paths.extend(root.parent / name for name in ("rubric/definition-of-ready.md", "AGENTS.md", ".github/agents/runtime-doc-contract.json"))
    try:
        return digest({str(p.name): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    except OSError as exc:
        raise ValidationError("Required policy source is missing") from exc


def _auth(db, token: str, roles=ROLES) -> dict:
    if not isinstance(token, str) or not re.fullmatch(r"[a-f0-9]{16}\.[A-Za-z0-9_-]{43}", token):
        raise ValidationError("Invalid or revoked capability")
    row = db.execute("SELECT * FROM credentials WHERE id=?", (token.split(".")[0],)).fetchone()
    hashed = hashlib.sha256(token.encode()).hexdigest()
    if row is None or not hmac.compare_digest(row["hash"], hashed) or not row["active"]:
        raise ValidationError("Invalid or revoked capability")
    if row["role"] not in roles:
        raise ValidationError("Capability does not permit this operation")
    return dict(row)


def provision(root: Path, actor: str, role: str, output: Path) -> str:
    """OS-owner administration, never exposed as an agent operation.

The secret is written exclusively to an operator-selected 0600 file, not stdout.
One actor cannot acquire both author and reviewer roles within this workspace.
"""
    identifier(actor)
    if role not in ROLES:
        raise ValidationError("Unknown capability role")
    key_id = secrets.token_hex(8)
    token = key_id + "." + secrets.token_urlsafe(32)
    with transaction(root) as db:
        existing = db.execute("SELECT role FROM credentials WHERE actor=?", (actor,)).fetchall()
        if any(row["role"] != role for row in existing):
            raise ValidationError("Actor role is fixed; use an independent reviewer identity")
        db.execute("INSERT INTO credentials(id,actor,role,hash) VALUES(?,?,?,?)", (key_id, actor, role, hashlib.sha256(token.encode()).hexdigest()))
        # On a crash/failed commit, the file may be an unusable orphan. It grants
        # nothing without its active DB record; do not overwrite it on retry.
        write_private(output, (token + "\n").encode())
    return key_id


def _run(db, run_id: str, expected: int | None = None):
    identifier(run_id)
    row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if row is None:
        raise ValidationError("Run not found")
    if expected is not None and (type(expected) is not int or row["version"] != expected):
        raise ValidationError("Stale run version; refresh before changing anything")
    return dict(row)


def _snapshot(db, run: dict) -> tuple[dict, dict]:
    row = db.execute("SELECT * FROM revisions WHERE run_id=? AND number=?", (run["id"], run["revision"])).fetchone()
    snapshot = json.loads(row["payload"])
    if digest(snapshot) != row["digest"]:
        raise ValidationError("Revision integrity check failed")
    return snapshot, dict(row)


def _event(db, run_id: str, actor: str, kind: str, data: dict):
    prev = db.execute("SELECT hash FROM events WHERE run_id=? ORDER BY sequence DESC LIMIT 1", (run_id,)).fetchone()
    body = {"run_id": run_id, "actor": actor, "kind": kind, "data": data, "created": time.time(), "previous_hash": prev[0] if prev else ""}
    db.execute("INSERT INTO events(run_id,actor,kind,data,created,previous_hash,hash) VALUES(?,?,?,?,?,?,?)", (run_id, actor, kind, canonical(data), body["created"], body["previous_hash"], digest(body)))


def _touch(db, run: dict, state: str, *, revoke: bool = True):
    if revoke:
        db.execute("UPDATE approvals SET revoked=1 WHERE run_id=? AND consumed=0", (run["id"],))
    db.execute("UPDATE runs SET version=version+1,state=?,updated=? WHERE id=?", (state, time.time(), run["id"]))


def _owner(db, run, actor):
    owner = db.execute("SELECT author FROM revisions WHERE run_id=? AND number=1", (run["id"],)).fetchone()[0]
    if owner != actor:
        raise ValidationError("Only the run's author may replace its draft")


def _pending(db, run: dict, snapshot: dict) -> list[str]:
    pending = []
    for row in db.execute("SELECT * FROM questions WHERE run_id=? ORDER BY id", (run["id"],)):
        if row["answer"] is None or row["id"] not in snapshot["acknowledged_answers"] or run["revision"] <= row["answered_revision"]:
            pending.append(row["id"])
    try:
        pending.extend(open_questions(snapshot["description"], snapshot["acceptance_criteria"]))
    except ValidationError:
        pending.append("Malformed question marker")
    return pending


def _plan(db, run: dict) -> dict:
    snapshot, revision = _snapshot(db, run)
    row = db.execute("SELECT * FROM reviews WHERE run_id=? AND revision=? ORDER BY id DESC LIMIT 1", (run["id"], run["revision"])).fetchone()
    if row is None:
        raise ValidationError("Independent review required")
    review = json.loads(row["payload"])
    if digest(review) != row["digest"]:
        raise ValidationError("Review integrity check failed")
    if review["result"]["verdict"] != "READY" or _pending(db, run, snapshot):
        raise ValidationError("Requirement is not READY")
    # Recompute actual lint at approval/export; changing rules or the dependency
    # cannot silently reuse a previous PASS.
    actual = lint.check(snapshot)
    if actual != review["lint"] or actual["injection_flags"] or review.get("policy_digest") != policy_digest():
        raise ValidationError("Checks changed; independent review required")
    return {"schema_version": 1, "action": "seal_local_export", "target": "local-workspace", "run_id": run["id"], "revision": run["revision"], "source_revision": snapshot["source"]["revision"], "snapshot_digest": revision["digest"], "review_digest": row["digest"], "policy_version": POLICY_VERSION, "lint_version": lint.LINT_VERSION, "policy_digest": policy_digest()}


class Workflow:
    def __init__(self, root: Path):
        self.root = Path(root)

    def create(self, token: str, run_id: str, value: dict) -> dict:
        snapshot = document(value)
        identifier(run_id)
        if snapshot["acknowledged_answers"]:
            raise ValidationError("New runs cannot claim previously approved answers")
        with transaction(self.root) as db:
            who = _auth(db, token, {"author"})
            if db.execute("SELECT 1 FROM runs WHERE id=?", (run_id,)).fetchone():
                raise ValidationError("Run ID already exists; resume it")
            for row in db.execute("SELECT v.payload FROM runs r JOIN revisions v ON v.run_id=r.id AND v.number=r.revision WHERE r.project=? AND r.state NOT IN ('rejected','exported')", (snapshot["project"],)):
                old = json.loads(row[0])
                if old["source"]["id"] == snapshot["source"]["id"]:
                    raise ValidationError("An active run already exists for this source; resume it")
            state = "quarantined" if lint.injection_flags(snapshot) else "awaiting_review"
            now = time.time()
            db.execute("INSERT INTO runs(id,project,state,version,revision,created,updated) VALUES(?,?,?,1,1,?,?)", (run_id, snapshot["project"], state, now, now))
            db.execute("INSERT INTO revisions VALUES(?,?,?,?,?,?)", (run_id, 1, who["actor"], canonical(snapshot), digest(snapshot), now))
            for question in snapshot["questions"]:
                db.execute("INSERT INTO questions(run_id,id,text) VALUES(?,?,?)", (run_id, question["id"], question["text"]))
            _event(db, run_id, who["actor"], "created", {"snapshot_digest": digest(snapshot), "state": state})
            return _run(db, run_id)

    def revise(self, token: str, run_id: str, expected_version: int, value: dict) -> dict:
        snapshot = document(value)
        with transaction(self.root) as db:
            who = _auth(db, token, {"author"})
            run = _run(db, run_id, expected_version)
            _owner(db, run, who["actor"])
            if run["state"] in TERMINAL or run["rewrites"] >= 3:
                raise ValidationError("Run closed or rewrite budget exhausted; operator decision required")
            old, _ = _snapshot(db, run)
            if snapshot["project"] != run["project"] or snapshot["source"]["id"] != old["source"]["id"]:
                raise ValidationError("Run project and source identity are immutable")
            if snapshot["source"]["text"] != old["source"]["text"] and snapshot["source"]["revision"] == old["source"]["revision"]:
                raise ValidationError("Changed source text needs a new source revision")
            known = {q["id"]: dict(q) for q in db.execute("SELECT * FROM questions WHERE run_id=?", (run_id,))}
            candidate = {q["id"]: q["text"] for q in snapshot["questions"]}
            for qid in snapshot["acknowledged_answers"]:
                if qid not in known or known[qid]["answer"] is None:
                    raise ValidationError("Cannot acknowledge an unconfirmed owner answer")
                if qid in candidate:
                    raise ValidationError("Answered question cannot also remain in open questions")
            for qid, prior in known.items():
                if qid not in candidate and qid not in snapshot["acknowledged_answers"]:
                    raise ValidationError("Question silently removed; owner answer and acknowledgment required")
                if qid in candidate and candidate[qid] != prior["text"]:
                    raise ValidationError("Question IDs cannot be repurposed")
            for qid, question in candidate.items():
                if qid not in known:
                    db.execute("INSERT INTO questions(run_id,id,text) VALUES(?,?,?)", (run_id, qid, question))
            revision = run["revision"] + 1
            db.execute("INSERT INTO revisions VALUES(?,?,?,?,?,?)", (run_id, revision, who["actor"], canonical(snapshot), digest(snapshot), time.time()))
            state = "quarantined" if run["state"] == "quarantined" or lint.injection_flags(snapshot) else "awaiting_review"
            _touch(db, run, state)
            db.execute("UPDATE runs SET revision=?,rewrites=rewrites+1 WHERE id=?", (revision, run_id))
            _event(db, run_id, who["actor"], "revised", {"revision": revision, "snapshot_digest": digest(snapshot)})
            return _run(db, run_id)

    def review(self, token: str, run_id: str, expected_version: int, value: dict) -> dict:
        with transaction(self.root) as db:
            who = _auth(db, token, {"reviewer"})
            run = _run(db, run_id, expected_version)
            if run["state"] not in {"awaiting_review", "awaiting_revision", "awaiting_po", "awaiting_approval", "approved"}:
                raise ValidationError("Run cannot be reviewed in its current state")
            if db.execute("SELECT 1 FROM revisions WHERE run_id=? AND author=?", (run_id, who["actor"])).fetchone():
                raise ValidationError("A draft author cannot independently review the same run")
            snapshot, revision = _snapshot(db, run)
            semantic = assessment(value, snapshot, revision["digest"])
            checked = lint.check(snapshot)
            unresolved_evidence = ["Evidence " + e["id"] + " is " + e["status"] for e in snapshot["evidence"] if e["status"] != "confirmed"]
            report = {"dimensions": {key: item["status"] for key, item in semantic["dimensions"].items()}, "checks": {key: item["status"] for key, item in checked["checks"].items()}, "open_questions": _pending(db, run, snapshot) + snapshot["investigation"]["missing"] + snapshot["investigation"]["conflicts"], "unconfirmed_proposals": snapshot["proposals"] + unresolved_evidence, "interface_touched": snapshot["interface_touched"], "regulated": snapshot["regulated"], "injection_detected": bool(checked["injection_flags"])}
            result = readiness(report)
            payload = {"policy_digest": policy_digest(), "assessment": semantic, "lint": checked, "report": report, "result": result, "reviewer": who["actor"]}
            db.execute("INSERT INTO reviews(run_id,revision,reviewer,payload,digest,created) VALUES(?,?,?,?,?,?)", (run_id, run["revision"], who["actor"], canonical(payload), digest(payload), time.time()))
            state = "quarantined" if checked["injection_flags"] else "awaiting_approval" if result["verdict"] == "READY" else "awaiting_po" if report["open_questions"] else "awaiting_revision"
            _touch(db, run, state)
            _event(db, run_id, who["actor"], "reviewed", {"review_digest": digest(payload), "verdict": result["verdict"], "state": state})
            return {"run": _run(db, run_id), "review": payload}

    def answer(self, token: str, run_id: str, expected_version: int, question_id: str, answer: str) -> dict:
        text(answer, "owner answer")
        if len(answer) > 10000:
            raise ValidationError("Owner answer exceeds size limit")
        with transaction(self.root) as db:
            who = _auth(db, token, {"operator"})
            run = _run(db, run_id, expected_version)
            if run["state"] in TERMINAL or run["state"] == "quarantined":
                raise ValidationError("Run is closed or quarantined")
            q = db.execute("SELECT * FROM questions WHERE run_id=? AND id=?", (run_id, question_id)).fetchone()
            if q is None:
                raise ValidationError("Unknown question ID")
            db.execute("UPDATE questions SET answer=?,answered_by=?,answered_revision=? WHERE run_id=? AND id=?", (answer, who["actor"], run["revision"], run_id, question_id))
            _touch(db, run, "awaiting_revision")
            _event(db, run_id, who["actor"], "owner_answered", {"question_id": question_id, "answer": answer, "supersedes_answer": q["answer"] is not None})
            return _run(db, run_id)

    def decide(self, token: str, run_id: str, expected_version: int, decision: str, reason: str) -> dict:
        text(reason, "decision reason")
        if decision not in {"reject", "release_quarantine", "new_rewrite_cycle"}:
            raise ValidationError("Unknown operator decision")
        with transaction(self.root) as db:
            who = _auth(db, token, {"operator"})
            run = _run(db, run_id, expected_version)
            if run["state"] in TERMINAL:
                raise ValidationError("Run is closed")
            if decision == "release_quarantine":
                snapshot, _ = _snapshot(db, run)
                if run["state"] != "quarantined" or lint.injection_flags(snapshot):
                    raise ValidationError("Quarantine needs a clean revision and explicit operator review")
                state = "awaiting_review"
            elif decision == "new_rewrite_cycle":
                if run["rewrites"] < 3:
                    raise ValidationError("Current rewrite budget has not been exhausted")
                db.execute("UPDATE runs SET rewrites=0 WHERE id=?", (run_id,))
                state = "quarantined" if run["state"] == "quarantined" else "awaiting_review"
            else:
                state = "rejected"
            _touch(db, run, state)
            _event(db, run_id, who["actor"], decision, {"reason": reason})
            return _run(db, run_id)

    def plan(self, token: str, run_id: str) -> dict:
        with transaction(self.root) as db:
            _auth(db, token)
            run = _run(db, run_id)
            if run["state"] not in {"awaiting_approval", "approved"}:
                raise ValidationError("No approvable plan in this state")
            plan = _plan(db, run)
            return {"plan": plan, "digest": digest(plan), "version": run["version"]}

    def approve(self, token: str, run_id: str, expected_version: int, expected_plan_digest: str, ttl: int = 900) -> dict:
        if type(ttl) is not int or not 1 <= ttl <= 900:
            raise ValidationError("Approval TTL must be 1 to 900 seconds")
        with transaction(self.root) as db:
            who = _auth(db, token, {"operator"})
            run = _run(db, run_id, expected_version)
            if run["state"] not in {"awaiting_approval", "approved"}:
                raise ValidationError("Independent READY review required before approval")
            plan = _plan(db, run)
            if digest(plan) != expected_plan_digest:
                raise ValidationError("Displayed plan changed; inspect it again")
            approval_id = "APP-" + secrets.token_hex(12)
            now = time.time()
            _touch(db, run, "approved")
            db.execute("INSERT INTO approvals(id,run_id,revision,approver,credential_id,plan,digest,issued,expires) VALUES(?,?,?,?,?,?,?,?,?)", (approval_id, run_id, run["revision"], who["actor"], who["id"], canonical(plan), digest(plan), now, now + ttl))
            _event(db, run_id, who["actor"], "approved", {"approval_id": approval_id, "plan_digest": digest(plan), "expires": now + ttl})
            return {"approval_id": approval_id, "plan_digest": digest(plan), "expires": now + ttl, "run": _run(db, run_id)}

    def seal(self, token: str, approval_id: str) -> dict:
        """Consume approval and store the immutable local export in ONE transaction.

A repeat returns the same stored bytes/digest. No filesystem or network side
 effect occurs during this commit. Later retrieval can safely be retried.
"""
        with transaction(self.root) as db:
            who = _auth(db, token, {"operator"})
            row = db.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
            if row is None or row["approver"] != who["actor"]:
                raise ValidationError("Approval not found for this operator")
            if row["consumed"]:
                old = db.execute("SELECT * FROM exports WHERE approval_id=?", (approval_id,)).fetchone()
                if old is None:
                    raise ValidationError("Approval/export integrity failure")
                return {"export_id": old["id"], "digest": old["digest"], "replayed": True}
            credential = db.execute("SELECT active FROM credentials WHERE id=?", (row["credential_id"],)).fetchone()
            if row["revoked"] or not credential or not credential[0] or not row["issued"] <= time.time() < row["expires"]:
                raise ValidationError("Approval expired or revoked; inspect and approve again")
            run = _run(db, row["run_id"])
            if run["state"] != "approved" or run["revision"] != row["revision"] or digest(_plan(db, run)) != row["digest"]:
                raise ValidationError("Approved plan is no longer current")
            snapshot, _ = _snapshot(db, run)
            history = [dict(r) for r in db.execute("SELECT number,author,payload,digest,created FROM revisions WHERE run_id=? ORDER BY number", (run["id"],))]
            reviews = [dict(r) for r in db.execute("SELECT revision,reviewer,payload,digest,created FROM reviews WHERE run_id=? ORDER BY id", (run["id"],))]
            events = [dict(r) for r in db.execute("SELECT * FROM events WHERE run_id=? ORDER BY sequence", (run["id"],))]
            export = {"schema_version": 1, "kind": "approved-local-requirement", "remote_published": False, "snapshot": snapshot, "plan": json.loads(row["plan"]), "approval": {"id": approval_id, "actor": who["actor"], "issued": row["issued"], "expires": row["expires"]}, "revisions": history, "reviews": reviews, "questions": [dict(q) for q in db.execute("SELECT * FROM questions WHERE run_id=? ORDER BY id", (run["id"],))], "events_before_seal": events}
            encoded = canonical(export)
            export_digest = digest(export)
            export_id = "EXP-" + secrets.token_hex(12)
            db.execute("INSERT INTO exports VALUES(?,?,?,?,?,?)", (export_id, approval_id, run["id"], encoded, export_digest, time.time()))
            db.execute("UPDATE approvals SET consumed=1 WHERE id=?", (approval_id,))
            _touch(db, run, "exported", revoke=False)
            _event(db, run["id"], who["actor"], "sealed_local_export", {"export_id": export_id, "digest": export_digest})
            return {"export_id": export_id, "digest": export_digest, "replayed": False}

    def export(self, token: str, export_id: str) -> str:
        with transaction(self.root) as db:
            _auth(db, token)
            row = db.execute("SELECT payload,digest FROM exports WHERE id=?", (export_id,)).fetchone()
            if row is None or digest(json.loads(row[0])) != row[1]:
                raise ValidationError("Export absent or integrity check failed")
            return row[0]

    def status(self, token: str, run_id: str) -> dict:
        with transaction(self.root) as db:
            _auth(db, token)
            run = _run(db, run_id)
            snapshot, revision = _snapshot(db, run)
            reviews = db.execute("SELECT payload FROM reviews WHERE run_id=? AND revision=? ORDER BY id DESC LIMIT 1", (run_id, run["revision"])).fetchone()
            proposed_plan = None
            plan_error = None
            if run["state"] in {"awaiting_approval", "approved"}:
                try:
                    p = _plan(db, run)
                    proposed_plan = {"plan": p, "digest": digest(p), "version": run["version"]}
                except ValidationError as exc:
                    plan_error = str(exc)
            return {"proposed_plan": proposed_plan, "plan_error": plan_error, "run": run, "snapshot": snapshot, "snapshot_digest": revision["digest"], "pending_questions": _pending(db, run, snapshot), "questions": [dict(q) for q in db.execute("SELECT * FROM questions WHERE run_id=? ORDER BY id", (run_id,))], "review": json.loads(reviews[0]) if reviews else None, "events": [dict(e) for e in db.execute("SELECT * FROM events WHERE run_id=? ORDER BY sequence", (run_id,))]}

    def list_runs(self, token: str) -> list[dict]:
        with transaction(self.root) as db:
            _auth(db, token)
            return [dict(row) for row in db.execute("SELECT * FROM runs ORDER BY updated DESC")]

    def revoke(self, token: str, credential_id: str):
        with transaction(self.root) as db:
            who = _auth(db, token, {"operator"})
            if credential_id == who["id"]:
                raise ValidationError("Cannot revoke the active administrative capability")
            if not db.execute("SELECT 1 FROM credentials WHERE id=?", (credential_id,)).fetchone():
                raise ValidationError("Credential not found")
            db.execute("UPDATE credentials SET active=0 WHERE id=?", (credential_id,))
            for approval in db.execute("SELECT * FROM approvals WHERE credential_id=? AND consumed=0 AND revoked=0", (credential_id,)).fetchall():
                run = _run(db, approval["run_id"])
                _touch(db, run, "awaiting_approval")
                _event(db, run["id"], who["actor"], "approval_credential_revoked", {"approval_id": approval["id"]})

    def verify(self, token: str, run_id: str) -> dict:
        with transaction(self.root) as db:
            _auth(db, token)
            run = _run(db, run_id)
            previous = ""
            count = 0
            for event in db.execute("SELECT * FROM events WHERE run_id=? ORDER BY sequence", (run_id,)):
                value = {k: event[k] for k in ("run_id", "actor", "kind", "created", "previous_hash")}
                value["data"] = json.loads(event["data"])
                if event["previous_hash"] != previous or digest(value) != event["hash"]:
                    raise ValidationError("Event chain integrity check failed")
                previous = event["hash"]
                count += 1
            for table in ("revisions", "reviews", "exports"):
                for row in db.execute("SELECT payload,digest FROM " + table + " WHERE run_id=?", (run_id,)):
                    if digest(json.loads(row[0])) != row[1]:
                        raise ValidationError("Stored artifact integrity check failed")
            return {"run_id": run["id"], "events": count, "head_hash": previous, "valid": True, "scope": "Accidental corruption detection; not tamper-proof against the OS/database owner"}
