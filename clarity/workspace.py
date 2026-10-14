"""Versioned local configuration, selected source library and encrypted credentials."""
import json
import secrets
import sqlite3
import time
import math
from datetime import date
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from .guardrails import canonical, digest, identifier, ValidationError
from .storage import transaction, private_path, write_private
from .refine.contracts import fields, require, text
from .refine.identity import authenticate

DDL = (
    'CREATE TABLE workspace_meta(version INTEGER NOT NULL)',
    'INSERT INTO workspace_meta VALUES(1)',
    'CREATE TABLE workspace_records(seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, id TEXT NOT NULL, actor TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL, created REAL NOT NULL)',
    'CREATE INDEX workspace_records_object ON workspace_records(kind,id,seq)',
    "CREATE TRIGGER workspace_records_no_update BEFORE UPDATE ON workspace_records BEGIN SELECT RAISE(ABORT,'immutable'); END",
    "CREATE TRIGGER workspace_records_no_delete BEFORE DELETE ON workspace_records BEGIN SELECT RAISE(ABORT,'append only'); END",
    'CREATE TABLE workspace_secrets(id TEXT PRIMARY KEY, ciphertext BLOB NOT NULL)',
    'CREATE TABLE workspace_jobs(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, actor TEXT NOT NULL, stage TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL, message TEXT NOT NULL)',
)
TABLES = ('workspace_meta', 'workspace_records', 'workspace_jobs')


def initialize(root):
    with transaction(Path(root)) as db:
        found = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'workspace_%'")}
        if found:
            require(found == {'workspace_meta', 'workspace_records', 'workspace_secrets', 'workspace_jobs'}, 'Incomplete workspace configuration namespace; restore or reconcile it')
            require([r[0] for r in db.execute('SELECT version FROM workspace_meta')] == [1], 'Unsupported workspace configuration schema')
            return
        for statement in DDL: db.execute(statement)


class Workspace:
    def __init__(self, root):
        self.root = Path(root)

    def actor(self, token, roles=None):
        with transaction(self.root, write=False) as db:
            return authenticate(db, token) if roles is None else authenticate(db, token, roles)

    def _cipher(self, create=False):
        path = self.root / 'vault.key'
        if not path.exists():
            require(create, 'Credential vault key is missing; reconnect this service')
            try: write_private(path, Fernet.generate_key())
            except FileExistsError: pass
        private_path(path)
        try: return Fernet(path.read_bytes())
        except (ValueError, TypeError): raise ValidationError('Credential vault key is invalid; restore the retained key or reconnect services') from None

    def secret(self, key_id):
        if not key_id: return ''
        with transaction(self.root, write=False) as db:
            row = db.execute('SELECT ciphertext FROM workspace_secrets WHERE id=?', (key_id,)).fetchone()
        require(row is not None, 'Connection requires a new credential after restore')
        try: return self._cipher().decrypt(row[0]).decode()
        except InvalidToken: raise ValidationError('Credential could not be decrypted; reconnect this service') from None

    def records(self, token, kind):
        self.actor(token)
        require(kind in {'model', 'connection', 'source', 'check'}, 'Unknown configuration section')
        with transaction(self.root, write=False) as db:
            result = {}
            for row in db.execute('SELECT * FROM workspace_records WHERE kind=? ORDER BY seq', (kind,)):
                data = json.loads(row['payload']); require(digest(data) == row['digest'], 'Workspace record integrity failure')
                result[row['id']] = {**data, 'id': row['id'], 'version': row['seq']}
            for value in result.values():
                key = value.get('secret_id')
                if 'secret_id' in value:
                    value['secret_present'] = bool(key and db.execute('SELECT 1 FROM workspace_secrets WHERE id=?', (key,)).fetchone())
                    value.pop('secret_id')
            return list(result.values())

    def _raw(self, db, kind, object_id):
        row = db.execute('SELECT * FROM workspace_records WHERE kind=? AND id=? ORDER BY seq DESC LIMIT 1', (kind, object_id)).fetchone()
        if row:
            data = json.loads(row['payload']); require(digest(data) == row['digest'], 'Workspace record integrity failure')
            return data, row['seq']
        return {}, 0

    def get(self, token, kind, object_id):
        self.actor(token)
        with transaction(self.root, write=False) as db:
            data, version = self._raw(db, kind, object_id)
            require(bool(version), 'Selected configuration record does not exist')
            return data, version

    def save(self, token, kind, object_id, expected, value, credential='', clear_credential=False):
        identifier(object_id)
        require(type(expected) is int and expected >= 0, 'Invalid configuration version')
        require(type(clear_credential) is bool and not (clear_credential and credential), 'Choose either a new credential or clearing the saved credential')
        roles = {'author', 'operator'} if kind == 'source' else {'operator'}
        who = self.actor(token, roles)
        value = json.loads(canonical(value))
        if kind == 'model':
            fields(value, {'provider', 'model', 'port', 'max_tokens', 'timeout', 'keep_alive', 'allow_cloud', 'enabled'}, 'model configuration')
            require(value['provider'] in {'host-assistant', 'ollama', 'local-openai', 'openai', 'anthropic'}, 'Choose a supported model connection')
            text(value['model'], 'model or assistant name', 200)
            require(type(value['port']) is int and 1 <= value['port'] <= 65535, 'Invalid local model port')
            require(type(value['max_tokens']) is int and 256 <= value['max_tokens'] <= 16384, 'Output budget must be 256-16384 tokens')
            require(type(value['timeout']) is int and 5 <= value['timeout'] <= 120, 'Timeout must be 5-120 seconds')
            require(type(value['keep_alive']) is int and 0 <= value['keep_alive'] <= 600, 'Keep-alive must be 0-600 seconds')
            require(type(value['allow_cloud']) is bool and type(value['enabled']) is bool, 'Invalid model switches')
            require(value['provider'] not in {'openai', 'anthropic'} or value['allow_cloud'], 'Explicitly allow selected evidence to be sent to this cloud provider')
        elif kind == 'connection':
            fields(value, {'provider', 'host', 'username', 'scope', 'project_scope', 'enabled'}, 'source connection')
            require(value['provider'] in {'linear', 'jira-cloud', 'confluence-cloud'}, 'Choose a supported source provider')
            identifier(value['scope'])
            if value['project_scope']: identifier(value['project_scope'])
            text(value['username'] or '-', 'connection username', 300)
            require(type(value['enabled']) is bool, 'Invalid connection switch')
            if value['provider'] != 'linear':
                from .connections import tenant_host
                tenant_host(value['host'])
        elif kind == 'source':
            fields(value, {'project', 'title', 'text', 'locator', 'revision', 'effective_date', 'retrieved_at'}, 'source library item')
            identifier(value['project']); text(value['title'], 'source title', 300); text(value['text'], 'source text', 100000); text(value['locator'], 'source locator', 2000)
            require(len(value['text'].encode()) <= 100000, 'Source text exceeds 100 KB; capture a smaller excerpt')
            text(value['revision'] or 'manual', 'source revision', 200)
            require(isinstance(value['effective_date'], str) and type(value['retrieved_at']) in (int, float) and math.isfinite(value['retrieved_at']), 'Invalid source dates')
            if value['effective_date']:
                try: date.fromisoformat(value['effective_date'])
                except ValueError: raise ValidationError('Use an ISO date for the effective date') from None
        elif kind == 'check':
            fields(value, {'connection', 'connection_version', 'status', 'message', 'checked_at'}, 'connection result')
            identifier(value['connection']); text(value['message'], 'diagnostic message', 2000)
            require(value['status'] in {'passed', 'failed'} and type(value['connection_version']) is int and type(value['checked_at']) in (int, float), 'Invalid diagnostic result')
        else: raise ValidationError('Unknown configuration section')
        if credential:
            text(credential, 'connection credential', 4000)
            require('\n' not in credential and '\r' not in credential, 'Invalid credential')
            cipher = self._cipher(create=True)
        with transaction(self.root) as db:
            authenticate(db, token, roles)
            prior, version = self._raw(db, kind, object_id)
            require(version == expected, 'Configuration changed; refresh before saving')
            if kind in {'model', 'connection'}:
                binding = ('provider', 'host', 'username') if kind == 'connection' else ('provider', 'port')
                unchanged = all(prior.get(k) == value.get(k) for k in binding)
                value['secret_id'] = prior.get('secret_id', '') if unchanged and not clear_credential else ''
                if credential:
                    key_id = secrets.token_hex(16)
                    db.execute('INSERT INTO workspace_secrets VALUES(?,?)', (key_id, cipher.encrypt(credential.encode())))
                    value['secret_id'] = key_id
            db.execute('INSERT INTO workspace_records(kind,id,actor,payload,digest,created) VALUES(?,?,?,?,?,?)', (kind, object_id, who['actor'], canonical(value), digest(value), time.time()))
        return object_id

    def probe(self, token, connection_id, expected):
        self.actor(token, {'operator'})
        _, version = self.get(token, 'model', connection_id)
        require(version == expected, 'Model profile changed; refresh before testing')
        provider = self.provider(token, connection_id)
        started = time.monotonic()
        schema = {'type': 'object', 'properties': {'ready': {'type': 'boolean'}}, 'required': ['ready'], 'additionalProperties': False}
        try:
            value = provider.complete('Return exactly the requested JSON, with ready=true. No tools.', {'task': 'synthetic_protocol_check', 'response_schema': schema})
            require(value == {'ready': True}, 'Provider did not return the requested structured result')
            state, message = 'passed', 'Synthetic structured output passed in %.2fs. This is not a requirement-quality evaluation.' % (time.monotonic() - started)
        except ValidationError as exc:
            state, message = 'failed', str(exc)
        check_id = 'CHECK-' + secrets.token_hex(6)
        self.save(token, 'check', check_id, 0, {'connection': connection_id, 'connection_version': version, 'status': state, 'message': message, 'checked_at': time.time()})
        return check_id

    def provider(self, token, connection_id):
        value, _ = self.get(token, 'model', connection_id)
        require(value['enabled'], 'Model connection is disabled')
        common = {'timeout': value['timeout'], 'max_tokens': value['max_tokens']}
        kind = value['provider']
        if kind == 'host-assistant':
            raise ValidationError('Use the host-assistant task/MCP bridge for Copilot, Codex or Claude Code')
        if kind == 'ollama':
            from .refine.worker import Ollama
            return Ollama(value['model'], port=value['port'], keep_alive=value['keep_alive'], **common)
        if kind == 'local-openai':
            from .local_model import LocalModel
            return LocalModel(value['model'], port=value['port'], key=self.secret(value.get('secret_id')), **common)
        require(value['allow_cloud'], 'Cloud sharing permission is disabled')
        from .connections import CloudModel
        return CloudModel(kind, value['model'], self.secret(value.get('secret_id')), **common)

    def import_source(self, token, connection_id, item, project):
        self.actor(token, {'author', 'operator'})
        value, _ = self.get(token, 'connection', connection_id)
        require(value['enabled'], 'Source connection is disabled')
        from .connections import read_source
        result = read_source(value, self.secret(value.get('secret_id')), item)
        source_id = 'SRC-' + secrets.token_hex(6)
        self.save(token, 'source', source_id, 0, {'project': project, **result, 'effective_date': ''})
        return source_id

    def attach(self, token, run_id, expected, source_id, supersedes='', expected_source_version=None):
        from .refine.controller import Controller
        c = Controller(self.root); status = c.status(token, run_id)
        source, version = self.get(token, 'source', source_id)
        require(expected_source_version is None or version == expected_source_version, 'Source library version changed; refresh before attaching')
        require(source['project'] == status['run']['project'], 'Source belongs to another project')
        target_id = source_id + '-' + str(version)
        args = (target_id, source['title'], source['text'], source['locator'])
        return c.replace_source(token, run_id, expected, supersedes, *args) if supersedes else c.add_source(token, run_id, expected, *args)
