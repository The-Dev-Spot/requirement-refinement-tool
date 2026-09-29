"""Private local SQLite storage with explicit transactions and no destructive upgrade."""
from __future__ import annotations

import os
import sqlite3
import stat
from contextlib import closing, contextmanager
from pathlib import Path

from .guardrails import ValidationError

SCHEMA = 1
DDL = """
CREATE TABLE credentials(id TEXT PRIMARY KEY, actor TEXT NOT NULL, role TEXT NOT NULL,
 hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE runs(id TEXT PRIMARY KEY, project TEXT NOT NULL, state TEXT NOT NULL,
 version INTEGER NOT NULL, revision INTEGER NOT NULL, rewrites INTEGER NOT NULL DEFAULT 0,
 created REAL NOT NULL, updated REAL NOT NULL);
CREATE TABLE revisions(run_id TEXT NOT NULL REFERENCES runs(id), number INTEGER NOT NULL,
 author TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL, created REAL NOT NULL,
 PRIMARY KEY(run_id, number));
CREATE TABLE questions(run_id TEXT NOT NULL REFERENCES runs(id), id TEXT NOT NULL,
 text TEXT NOT NULL, answer TEXT, answered_by TEXT, answered_revision INTEGER,
 PRIMARY KEY(run_id,id));
CREATE TABLE reviews(id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
 revision INTEGER NOT NULL, reviewer TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL,
 created REAL NOT NULL);
CREATE TABLE approvals(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
 revision INTEGER NOT NULL, approver TEXT NOT NULL, credential_id TEXT NOT NULL REFERENCES credentials(id),
 plan TEXT NOT NULL, digest TEXT NOT NULL, issued REAL NOT NULL, expires REAL NOT NULL,
 consumed INTEGER NOT NULL DEFAULT 0, revoked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE exports(id TEXT PRIMARY KEY, approval_id TEXT NOT NULL UNIQUE REFERENCES approvals(id),
 run_id TEXT NOT NULL REFERENCES runs(id), payload TEXT NOT NULL, digest TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE events(sequence INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES runs(id),
 actor TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL, created REAL NOT NULL,
 previous_hash TEXT NOT NULL, hash TEXT NOT NULL);
CREATE INDEX events_by_run ON events(run_id,sequence);
CREATE INDEX reviews_by_run ON reviews(run_id,revision,id);
CREATE TRIGGER revisions_no_update BEFORE UPDATE ON revisions BEGIN SELECT RAISE(ABORT,'immutable'); END;
CREATE TRIGGER revisions_no_delete BEFORE DELETE ON revisions BEGIN SELECT RAISE(ABORT,'immutable'); END;
CREATE TRIGGER events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'append only'); END;
CREATE TRIGGER events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'append only'); END;
CREATE TRIGGER reviews_no_update BEFORE UPDATE ON reviews BEGIN SELECT RAISE(ABORT,'immutable'); END;
CREATE TRIGGER reviews_no_delete BEFORE DELETE ON reviews BEGIN SELECT RAISE(ABORT,'immutable'); END;
CREATE TRIGGER exports_no_update BEFORE UPDATE ON exports BEGIN SELECT RAISE(ABORT,'immutable'); END;
CREATE TRIGGER exports_no_delete BEFORE DELETE ON exports BEGIN SELECT RAISE(ABORT,'immutable'); END;
PRAGMA user_version=1;
"""


def private_path(path: Path, *, directory: bool = False) -> None:
    """POSIX-only release: refuse symlinks, other owners and permissive modes."""
    if os.name != "posix":
        raise ValidationError("Secure local state currently requires POSIX permissions")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValidationError("Symlinked state paths are not allowed")
    st = path.stat()
    if st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise ValidationError("State must be owner-only (directory 0700, file 0600)")
    if directory and not stat.S_ISDIR(st.st_mode):
        raise ValidationError("State root is not a directory")
    if not directory and (not stat.S_ISREG(st.st_mode) or st.st_nlink != 1):
        raise ValidationError("Unsafe state file")


def initialize(root: Path) -> None:
    root = root.absolute()
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ValidationError("Symlinked state root")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    private_path(root, directory=True)
    target = root / "state.sqlite3"
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with closing(sqlite3.connect(target)) as db:
        db.executescript(DDL)


@contextmanager
def transaction(root: Path):
    root = root.absolute()
    private_path(root, directory=True)
    path = root / "state.sqlite3"
    private_path(path)
    for suffix in ("-wal", "-shm", "-journal"):
        sidecar = root / (path.name + suffix)
        if sidecar.exists() or sidecar.is_symlink():
            private_path(sidecar)
    db = sqlite3.connect(path, timeout=5, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        if db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA:
            raise ValidationError("Unsupported database schema; do not overwrite it")
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def write_private(path: Path, content: bytes) -> None:
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValidationError("Refusing symlinked output path")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
