"""Use the existing workspace capability format, never model-generated identities."""
from __future__ import annotations
import hashlib
import hmac
import re
import secrets
from pathlib import Path
from ..storage import transaction, write_private
from .contracts import require
from ..guardrails import identifier

ROLES = frozenset({"author", "reviewer", "operator"})


def authenticate(db, token: str, roles=ROLES) -> dict:
    require(isinstance(token, str) and bool(re.fullmatch(r"[a-f0-9]{16}\.[A-Za-z0-9_-]{43}", token)), "Invalid or revoked capability")
    row = db.execute("SELECT * FROM credentials WHERE id=?", (token.split('.')[0],)).fetchone()
    require(row is not None and row['active'] and hmac.compare_digest(row['hash'], hashlib.sha256(token.encode()).hexdigest()), "Invalid or revoked capability")
    require(row['role'] in roles, "Capability does not permit this action")
    return dict(row)


def provision(root: Path, actor: str, role: str, output: Path) -> str:
    """OS-owner-only CLI bootstrap, never exposed through HTTP or to a model."""
    identifier(actor)
    require(role in ROLES, "Invalid role")
    key_id = secrets.token_hex(8)
    token = key_id + '.' + secrets.token_urlsafe(32)
    with transaction(root) as db:
        roles = db.execute('SELECT role FROM credentials WHERE actor=?', (actor,)).fetchall()
        require(all(r[0] == role for r in roles), "An actor cannot assume multiple roles")
        db.execute('INSERT INTO credentials(id,actor,role,hash) VALUES(?,?,?,?)', (key_id, actor, role, hashlib.sha256(token.encode()).hexdigest()))
        write_private(output, (token + '\n').encode())
    return key_id
