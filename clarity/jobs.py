"""Bounded local inference jobs with durable status and cooperative cancellation."""
import secrets
import threading
import time
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

from .guardrails import ValidationError
from .refine.contracts import require
from .refine.controller import Controller
from .refine.identity import authenticate
from .refine.worker import prepare, run_stage
from .storage import transaction, private_path


class RuntimeLease:
    """One HTTP runtime per state directory; no stale PID guessing or deletion."""
    def __init__(self, root):
        import fcntl
        root = Path(root).absolute(); private_path(root, directory=True)
        path = root / 'runtime.lock'
        if path.exists() or path.is_symlink(): private_path(path)
        self.fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            private_path(path)
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(self.fd); self.fd = None
            raise ValidationError('This workspace is already running, or its runtime lock is unsafe') from None

    def close(self):
        if self.fd is not None:
            import fcntl
            fcntl.flock(self.fd, fcntl.LOCK_UN); os.close(self.fd); self.fd = None


class Jobs:
    def __init__(self, root):
        self.root = root; self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='clarity-model')
        self.lock = threading.Lock(); self.cancelled = {}
        with transaction(root) as db:
            db.execute("UPDATE workspace_jobs SET status='interrupted',message='The application stopped. Review state and explicitly retry.',updated=? WHERE status IN ('queued','running','applying','cancel_requested')", (time.time(),))

    def list(self, token, run_id):
        Controller(self.root).status(token, run_id)
        with transaction(self.root, write=False) as db:
            return [dict(r) for r in db.execute('SELECT * FROM workspace_jobs WHERE run_id=? ORDER BY created DESC LIMIT 10', (run_id,))]

    def start(self, token, run_id, expected, stage, provider):
        c = Controller(self.root); status = c.status(token, run_id)
        prepare(c, token, run_id, expected, stage, status)
        who = status['actor']; require(who['role'] == ('author' if stage == 'draft' else 'reviewer'), 'This role cannot run the selected stage')
        require(status['run']['version'] == expected, 'Refresh the requirement before starting inference')
        with self.lock:
            with transaction(self.root) as db:
                active = db.execute("SELECT COUNT(*) FROM workspace_jobs WHERE status IN ('queued','running','applying','cancel_requested')").fetchone()[0]
                require(active < 2, 'Two model jobs are already active; wait or cancel one')
                require(db.execute("SELECT 1 FROM workspace_jobs WHERE run_id=? AND status IN ('queued','running','applying','cancel_requested')", (run_id,)).fetchone() is None, 'This requirement already has an active model job')
                job_id = secrets.token_hex(12); now = time.time()
                db.execute('INSERT INTO workspace_jobs VALUES(?,?,?,?,?,?,?,?)', (job_id, run_id, who['name'], stage, 'queued', now, now, 'Waiting for the selected provider'))
            cancel = threading.Event(); self.cancelled[job_id] = cancel
            self.pool.submit(self._run, job_id, token, run_id, expected, stage, provider, cancel)
        return job_id

    def _update(self, job_id, status, message):
        with transaction(self.root) as db:
            db.execute('UPDATE workspace_jobs SET status=?,message=?,updated=? WHERE id=?', (status, message, time.time(), job_id))

    def _run(self, job_id, token, run_id, expected, stage, provider, cancel):
        @contextmanager
        def applying():
            with self.lock:
                require(not cancel.is_set(), 'Model operation cancelled; output was not applied')
                self._update(job_id, 'applying', 'Validating and recording the returned result')
                yield
        try:
            self._update(job_id, 'running', 'Inference is running; refresh this page to follow progress')
            run_stage(Controller(self.root), token, run_id, expected, stage, provider, cancelled=cancel.is_set, apply_guard=applying)
            self._update(job_id, 'completed', 'Result validated and recorded. Independent review and operator approval remain separate.')
        except ValidationError as exc:
            self._update(job_id, 'cancelled' if cancel.is_set() else 'failed', str(exc))
        except Exception:
            self._update(job_id, 'failed', 'The operation failed. Inspect the requirement and explicitly retry; no approval is implied.')
        finally:
            with self.lock: self.cancelled.pop(job_id, None)

    def cancel(self, token, job_id):
        with self.lock:
            with transaction(self.root) as db:
                who = authenticate(db, token)
                row = db.execute('SELECT * FROM workspace_jobs WHERE id=?', (job_id,)).fetchone()
                require(row is not None and (row['actor'] == who['actor'] or who['role'] == 'operator'), 'Job is unavailable for this actor')
                require(row['status'] in {'queued', 'running', 'cancel_requested'}, 'This job has finished inference; refresh to inspect its result')
                db.execute("UPDATE workspace_jobs SET status='cancel_requested',message='Cancellation requested. In-flight provider work may finish, but its output will not be applied.',updated=? WHERE id=?", (time.time(), job_id))
            if job_id in self.cancelled: self.cancelled[job_id].set()

    def close(self):
        with self.lock:
            for flag in self.cancelled.values(): flag.set()
        self.pool.shutdown(wait=True)
