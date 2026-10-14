"""Owner-run setup and local diagnostics; never an HTTP administration endpoint."""
import importlib.util
import json
from pathlib import Path
from .storage import initialize as base_initialize, private_path
from .refine.controller import initialize as refine_initialize, engine_digest
from .refine.identity import provision
from .workspace import initialize as settings_initialize
from .refine.contracts import require

DEFAULT_STATE = Path.home() / '.local' / 'share' / 'clarity'


def setup(root):
    root = root.absolute()
    if not (root / 'state.sqlite3').exists(): base_initialize(root)
    refine_initialize(root); settings_initialize(root)
    keys = root / 'keys'
    keys.mkdir(mode=0o700, exist_ok=True); private_path(keys, directory=True)
    paths = []
    for role in ('author', 'reviewer', 'operator'):
        path = keys / (role + '.key')
        if not path.exists(): provision(root, 'local-' + role, role, path)
        else: private_path(path)
        paths.append(str(path))
    return {'state': str(root), 'login_files': paths, 'next': 'clarity start --state ' + str(root)}


def doctor(root):
    private_path(root, directory=True); private_path(root / 'state.sqlite3')
    require(importlib.util.find_spec('gherkin') is not None, 'Official Gherkin parser is not installed')
    require(importlib.util.find_spec('cryptography') is not None, 'Credential encryption dependency is not installed')
    from .storage import transaction
    with transaction(root, write=False) as db:
        require(db.execute('PRAGMA quick_check').fetchone()[0] == 'ok', 'SQLite integrity check failed')
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        require({'refine_meta', 'workspace_meta'} <= tables, 'Run clarity setup to initialize the current application tables')
        active = [dict(r) for r in db.execute('SELECT role,COUNT(*) AS count FROM credentials WHERE active=1 GROUP BY role')]
    return {'state': str(root.absolute()), 'storage': 'ok', 'parser': 'installed', 'quality_contract': engine_digest(), 'active_roles': active,
            'network_checked': False, 'next': 'Open clarity start, then explicitly test your selected model in Setup.'}
