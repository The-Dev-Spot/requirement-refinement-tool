"""Durable brief-to-Gherkin controller on the existing private SQLite workspace.

Additive, versioned tables keep incomplete briefs out of the legacy snapshot API.
All mutations are authenticated and transactional. Models never receive keys.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import time
from pathlib import Path

from ..guardrails import ValidationError, canonical, digest, identifier
from ..storage import transaction
from . import checks
from .contracts import DEFAULT_POLICY, draft, fields, policy, require, review, source_record, text
from .identity import authenticate

TABLES = (
    "CREATE TABLE refine_meta(version INTEGER NOT NULL)",
    "INSERT INTO refine_meta VALUES(1)",
    "CREATE TABLE refine_runs(id TEXT PRIMARY KEY, project TEXT NOT NULL, owner TEXT NOT NULL, presentation TEXT NOT NULL, brief TEXT NOT NULL, version INTEGER NOT NULL, revision INTEGER NOT NULL DEFAULT 0, rewrites INTEGER NOT NULL DEFAULT 0, calls INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL, created REAL NOT NULL)",
    "CREATE TABLE refine_records(seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT REFERENCES refine_runs(id), kind TEXT NOT NULL, actor TEXT NOT NULL, credential_id TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL, previous_hash TEXT NOT NULL, hash TEXT NOT NULL, created REAL NOT NULL)",
    "CREATE TABLE refine_exports(approval_id INTEGER PRIMARY KEY REFERENCES refine_records(seq), run_id TEXT NOT NULL REFERENCES refine_runs(id), payload TEXT NOT NULL, digest TEXT NOT NULL)",
    "CREATE INDEX refine_records_run ON refine_records(run_id,kind,seq)",
    "CREATE TRIGGER refine_records_no_update BEFORE UPDATE ON refine_records BEGIN SELECT RAISE(ABORT,'immutable'); END",
    "CREATE TRIGGER refine_records_no_delete BEFORE DELETE ON refine_records BEGIN SELECT RAISE(ABORT,'append only'); END",
    "CREATE TRIGGER refine_exports_no_update BEFORE UPDATE ON refine_exports BEGIN SELECT RAISE(ABORT,'immutable'); END",
    "CREATE TRIGGER refine_exports_no_delete BEFORE DELETE ON refine_exports BEGIN SELECT RAISE(ABORT,'immutable'); END",
)


def initialize(root: Path) -> None:
    """Explicit OS-owner migration. Never runs in an agent tool or HTTP request."""
    with transaction(root) as db:
        found = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'refine_%'").fetchall()
        if found:
            require({r[0] for r in found} == {'refine_meta', 'refine_runs', 'refine_records', 'refine_exports'}, "Incomplete refinement schema; restore or reconcile, do not overwrite")
            _schema(db)
            return
        for statement in TABLES:
            db.execute(statement)


def _schema(db):
    rows = db.execute('SELECT version FROM refine_meta').fetchall()
    require(len(rows) == 1 and rows[0][0] == 1, "Unsupported refinement schema")


def engine_digest() -> str:
    package = Path(__file__).parents[1]
    root = package.parent
    resources = {'AGENTS.md': 'AGENTS.md', 'handoff-standard.md': 'docs/handoff-standard.md',
                 'runtime-doc-contract.json': '.github/agents/runtime-doc-contract.json', 'requirements.lock': 'requirements.lock'}
    try:
        hashes = {str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(package.rglob('*.py')) if 'resources' not in p.relative_to(package).parts}
        for name, source in resources.items():
            path = root / source if (root / 'pyproject.toml').is_file() else package / 'resources' / name
            hashes['contract/' + name] = hashlib.sha256(path.read_bytes()).hexdigest()
        return digest(hashes)
    except OSError as exc:
        raise ValidationError('A required quality-policy resource is missing') from exc


def _records(db, run_id, kind=None):
    query = 'SELECT * FROM refine_records WHERE run_id IS ?'
    args = [run_id]
    if kind:
        query += ' AND kind=?'; args.append(kind)
    rows = db.execute(query + ' ORDER BY seq', args).fetchall()
    result = []
    for row in rows:
        record = dict(row)
        record['data'] = json.loads(record['payload'])
        require(digest(record['data']) == record['digest'], "Stored refinement artifact failed integrity check")
        result.append(record)
    return result


def _record(db, run_id, who, kind, value):
    prior = db.execute('SELECT hash FROM refine_records WHERE run_id IS ? ORDER BY seq DESC LIMIT 1', (run_id,)).fetchone()
    now = time.time()
    payload = canonical(value)
    previous = prior[0] if prior else ''
    body = {'run_id': run_id, 'kind': kind, 'actor': who['actor'], 'credential_id': who['id'], 'digest': digest(value), 'previous_hash': previous, 'created': now}
    cur = db.execute('INSERT INTO refine_records(run_id,kind,actor,credential_id,payload,digest,previous_hash,hash,created) VALUES(?,?,?,?,?,?,?,?,?)', (run_id, kind, who['actor'], who['id'], payload, body['digest'], previous, digest(body), now))
    return cur.lastrowid


def _access(db, token, run_id, expected=None, roles=None):
    _schema(db)
    who = authenticate(db, token) if roles is None else authenticate(db, token, roles)
    identifier(run_id)
    row = db.execute('SELECT * FROM refine_runs WHERE id=?', (run_id,)).fetchone()
    require(row is not None, "Brief not found")
    run = dict(row)
    require(who['role'] != 'author' or run['owner'] == who['actor'], "Author cannot access another author's brief")
    if expected is not None:
        require(type(expected) is int and run['version'] == expected, "Stale brief version; refresh first")
        require(run['state'] not in {'exported', 'rejected'}, "Brief is closed")
    return who, run


def _touch(db, run, state):
    db.execute('UPDATE refine_runs SET version=version+1,state=? WHERE id=?', (state, run['id']))


def _policy(db, project):
    selected = {'project': project, 'policy': DEFAULT_POLICY, 'operator': 'built-in', 'record': 0}
    for item in _records(db, None, 'policy'):
        if item['data']['project'] == project:
            selected = {**item['data'], 'record': item['seq']}
    return selected


def _context(db, run):
    sources = {'BRIEF': source_record('BRIEF', 'Original request', run['brief'], 'local:brief:' + run['id'], 'request', run['owner'])}
    questions = {}
    for r in _records(db, run['id']):
        value = r['data']
        if r['kind'] == 'source':
            sources[value['id']] = value
        elif r['kind'] == 'source_authority':
            source = sources[value['source_id']]
            require(source['digest'] == value['source_digest'], "Reference authority is stale")
            sources[source['id']] = source_record(source['id'], source['title'], source['text'], source['locator'], 'reference', 'operator:' + r['actor'] + ':decision:' + str(r['seq']))
        elif r['kind'] == 'source_superseded':
            sources.pop(value['old_id'], None)
        elif r['kind'] == 'question':
            questions[value['id']] = {**value, 'state': 'open'}
        elif r['kind'] == 'answer':
            old_decision = questions[value['question_id']].get('decision_source')
            if old_decision:
                sources.pop(old_decision, None)
            questions[value['question_id']] = {**questions[value['question_id']], 'state': 'answered', 'decision_source': value['source']['id']}
            sources[value['source']['id']] = value['source']
        elif r['kind'] == 'question_resolution':
            questions[value['question_id']] = {**questions[value['question_id']], 'state': value['resolution'], 'reason': value['reason'], 'target': value['target']}
    return {'sources': sources, 'questions': questions, 'policy': _policy(db, run['project'])}


def _current(db, run):
    records = _records(db, run['id'], 'draft')
    require(bool(records), "No requirement draft exists yet")
    current = records[-1]
    context = _context(db, run)
    require(current['data']['context_digest'] == digest(context), "Evidence, decisions or policy changed; revise and re-review")
    require(current['data']['engine_digest'] == engine_digest(), "Quality rules changed; submit a fresh revision and review")
    return current, context


def _quality(db, run, current, context, reviewed):
    value = current['data']['draft']
    actual = checks.check(value, context['sources'], context['policy']['policy'])
    warning_ids = {f['id'] for f in actual['findings'] if f['severity'] == 'warning'}
    require(set(reviewed['warning_resolutions']) <= warning_ids, "Only current context-sensitive warnings can be resolved by a reviewer")
    cleared = set()
    for record in _records(db, run['id'], 'signal_resolution'):
        if record['data']['draft_digest'] == digest(value) and record['data']['context_digest'] == digest(context):
            cleared.add(record['data']['finding_id'])
    unresolved = [f for f in actual['findings'] if not (f['severity'] == 'warning' and f['id'] in reviewed['warning_resolutions']) and not (f['severity'] == 'security' and f['id'] in cleared)]
    blockers = [f['code'] + ':' + f['scope'] for f in unresolved]
    blockers += ['question:' + q['id'] for q in context['questions'].values() if q['state'] == 'open']
    for section in ('checks', 'statement_support', 'scenario_fidelity'):
        blockers += [section + ':' + key for key, result in reviewed[section].items() if result['status'] != 'PASS']
    if reviewed['ambiguities']:
        blockers.append('material_ambiguity')
    return {'verdict': 'READY' if not blockers else 'NOT READY', 'blockers': sorted(set(blockers)), 'machine': actual, 'resolved_signals': sorted(cleared), 'semantic_truth_verified': False}


def _ready(db, run):
    current, context = _current(db, run)
    reviews = _records(db, run['id'], 'review')
    require(bool(reviews), "Independent review is required")
    latest = reviews[-1]
    require(latest['data']['draft_record'] == current['seq'], "Review does not cover the current revision")
    credential = db.execute('SELECT active FROM credentials WHERE id=?', (latest['credential_id'],)).fetchone()
    require(credential is not None and credential[0], "Reviewing capability was revoked; obtain a new independent review")
    actual = _quality(db, run, current, context, latest['data']['review'])
    require(actual == latest['data']['quality'] and actual['verdict'] == 'READY', "Requirement is not READY or its checks changed")
    return current, context, latest


class Controller:
    def __init__(self, root: Path):
        self.root = Path(root)

    def create(self, token, run_id, project, brief, presentation='guided'):
        identifier(run_id); identifier(project); text(brief, 'brief', 50000)
        require(presentation in {'guided', 'concise'}, "Unknown presentation preference")
        with transaction(self.root) as db:
            _schema(db); who = authenticate(db, token, {'author'})
            require(db.execute('SELECT 1 FROM refine_runs WHERE id=?', (run_id,)).fetchone() is None, "Brief already exists; resume it")
            db.execute('INSERT INTO refine_runs(id,project,owner,presentation,brief,version,state,created) VALUES(?,?,?,?,?,1,?,?)', (run_id, project, who['actor'], presentation, brief, 'captured', time.time()))
            _record(db, run_id, who, 'captured', {'brief_digest': digest(brief), 'presentation': presentation})
        return self.status(token, run_id)

    def set_policy(self, token, project, value, expected_record=None):
        identifier(project); value = policy(value)
        with transaction(self.root) as db:
            _schema(db); who = authenticate(db, token, {'operator'})
            require(expected_record is None or _policy(db, project)['record'] == expected_record, 'Project policy changed; refresh before saving')
            return _record(db, None, who, 'policy', {'project': project, 'policy': value, 'operator': who['actor']})

    def add_source(self, token, run_id, expected, source_id, title, body, locator):
        value = source_record(source_id, title, body, locator, 'reference', None)
        with transaction(self.root) as db:
            who, run = _access(db, token, run_id, expected, {'author'})
            context = _context(db, run)
            require(len(context['sources']) < 21 and sum(len(s['text'].encode()) for s in context['sources'].values()) + len(body.encode()) <= 300000, "Selected source budget exceeded")
            require(source_id not in context['sources'] and not source_id.startswith('DEC-'), "Source ID is reserved or already captured; use a new revision ID")
            _record(db, run_id, who, 'source', value); _touch(db, run, 'awaiting_revision')
        return self.status(token, run_id)

    def confirm_source(self, token, run_id, expected, source_id, expected_digest, reason):
        require(len(text(reason, 'source applicability reason', 5000)) >= 20, "Explain source authority and scope")
        with transaction(self.root) as db:
            who, run = _access(db, token, run_id, expected, {'operator'})
            source = _context(db, run)['sources'].get(source_id)
            require(source is not None and source['kind'] == 'reference' and source['authority'] is None and source['digest'] == expected_digest, "Source is absent, already confirmed, or changed")
            _record(db, run_id, who, 'source_authority', {'source_id': source_id, 'source_digest': expected_digest, 'reason': reason})
            _touch(db, run, 'awaiting_revision')
        return self.status(token, run_id)

    def replace_source(self, token, run_id, expected, old_id, source_id, title, body, locator):
        value = source_record(source_id, title, body, locator, 'reference', None)
        with transaction(self.root) as db:
            who, run = _access(db, token, run_id, expected, {'author'})
            context = _context(db, run)
            require(old_id in context['sources'] and context['sources'][old_id]['kind'] == 'reference', 'Select a current reference to replace')
            require(source_id not in context['sources'] and not source_id.startswith('DEC-'), 'Use a new source revision ID')
            selected = [s for k, s in context['sources'].items() if k != old_id]
            require(sum(len(s['text'].encode()) for s in selected) + len(body.encode()) <= 300000, 'Selected source budget exceeded')
            _record(db, run_id, who, 'source', value)
            _record(db, run_id, who, 'source_superseded', {'old_id': old_id, 'new_id': source_id})
            _touch(db, run, 'awaiting_revision')
        return self.status(token, run_id)

    def ask(self, token, run_id, expected, value):
        return self.ask_many(token, run_id, expected, [value])

    def ask_many(self, token, run_id, expected, values, expected_context=None):
        require(isinstance(values, list) and 1 <= len(values) <= 5, "Ask between one and five targeted questions per batch")
        for value in values:
            fields(value, {'id', 'text', 'why', 'impact'}, 'question')
            identifier(value['id']); text(value['text'], 'question', 3000); text(value['why'], 'decision consequence', 3000)
            require(type(value['impact']) is int and 1 <= value['impact'] <= 5, "Question impact must be 1 to 5")
        with transaction(self.root) as db:
            who, run = _access(db, token, run_id, expected, {'author', 'reviewer'})
            context = _context(db, run)
            require(expected_context is None or digest(context) == expected_context, 'Evidence or policy changed; get a fresh assistant task')
            known = context['questions']
            require(len(known) + len(values) <= 100, "Question limit reached; consolidate with an owner decision")
            norm = lambda s: ' '.join(s.casefold().split())
            for value in values:
                require(value['id'] not in known, "Question IDs cannot be repurposed")
                require(all(norm(q['text']) != norm(value['text']) for q in known.values()), "This question was already asked; resume its answer or resolution")
                known[value['id']] = value
            for value in values:
                _record(db, run_id, who, 'question', value)
            _touch(db, run, 'awaiting_decision')
        return self.status(token, run_id)

    def answer(self, token, run_id, expected, question_id, answer):
        text(answer, 'owner answer', 10000)
        with transaction(self.root) as db:
            who, run = _access(db, token, run_id, expected, {'operator'})
            question = _context(db, run)['questions'].get(question_id)
            require(question is not None and question['state'] in {'open', 'answered'}, "Question is absent or has an explicit non-answer resolution")
            sid = 'DEC-' + secrets.token_hex(8)
            source = source_record(sid, 'Owner decision on ' + question_id, answer, 'local:decision:' + run_id + ':' + sid, 'decision', who['actor'])
            _record(db, run_id, who, 'answer', {'question_id': question_id, 'source': source})
            _touch(db, run, 'awaiting_revision')
        return self.status(token, run_id)

    def resolve_question(self, token, run_id, expected, question_id, resolution, target, reason):
        require(resolution in {'merged', 'out_of_scope'}, "Only explicit merge or out-of-scope resolutions are supported")
        require(len(text(reason, 'resolution rationale', 5000)) >= 20, "Explain the disposition")
        with transaction(self.root) as db:
            who, run = _access(db, token, run_id, expected, {'operator'})
            questions = _context(db, run)['questions']
            require(question_id in questions and questions[question_id]['state'] == 'open', "Only an open question may be resolved")
            if resolution == 'merged':
                require(isinstance(target, str) and target != question_id and target in questions and questions[target]['state'] == 'open', "Merge requires another open question and cannot create a cycle")
            else:
                require(target is None, "Out-of-scope resolution has no merge target")
            _record(db, run_id, who, 'question_resolution', {'question_id': question_id, 'resolution': resolution, 'target': target, 'reason': reason})
            _touch(db, run, 'awaiting_revision')
        return self.status(token, run_id)

    def submit(self, token, run_id, expected, value, expected_context=None):
        value = draft(value)
        with transaction(self.root) as db:
            who, run = _access(db, token, run_id, expected, {'author'})
            context = _context(db, run)
            require(expected_context is None or digest(context) == expected_context, 'Evidence or policy changed; get a fresh assistant task')
            require(run['rewrites'] < context['policy']['policy']['max_rewrites'] or run['revision'] == 0, "Rewrite budget exhausted; an operator must authorize another cycle")
            _record(db, run_id, who, 'draft', {'draft': value, 'context_digest': digest(context), 'engine_digest': engine_digest(), 'revision': run['revision'] + 1})
            db.execute('UPDATE refine_runs SET revision=revision+1,rewrites=rewrites+? WHERE id=?', (int(run['revision'] > 0), run_id))
            _touch(db, run, 'awaiting_review')
        return self.status(token, run_id)

    def review(self, token, run_id, expected, value):
        with transaction(self.root) as db:
            who, run = _access(db, token, run_id, expected, {'reviewer'})
            require(who['actor'] != run['owner'], "Draft author cannot independently review the same requirement")
            current, context = _current(db, run)
            value = review(value, current['data']['draft'], digest(current['data']['draft']))
            result = _quality(db, run, current, context, value)
            _record(db, run_id, who, 'review', {'draft_record': current['seq'], 'review': value, 'quality': result})
            _touch(db, run, 'awaiting_approval' if result['verdict'] == 'READY' else 'awaiting_revision')
        return self.status(token, run_id)

    def resolve_signal(self, token, run_id, expected, finding_id, reason):
        require(len(text(reason, 'false-positive rationale', 5000)) >= 20, "Explain why this exact instruction signal is benign")
        with transaction(self.root) as db:
            who, run = _access(db, token, run_id, expected, {'operator'})
            current, context = _current(db, run)
            value = current['data']['draft']
            actual = checks.check(value, context['sources'], context['policy']['policy'])
            require(finding_id in {f['id'] for f in actual['findings'] if f['severity'] == 'security'}, "Only a current instruction signal can be resolved; objective failures cannot be bypassed")
            _record(db, run_id, who, 'signal_resolution', {'finding_id': finding_id, 'draft_digest': digest(value), 'context_digest': digest(context), 'reason': reason})
            _touch(db, run, 'awaiting_review')
        return self.status(token, run_id)

    def new_cycle(self, token, run_id, expected, reason):
        require(len(text(reason, 'new-cycle rationale', 5000)) >= 20, "Explain the new refinement cycle")
        with transaction(self.root) as db:
            who, run = _access(db, token, run_id, expected, {'operator'})
            _record(db, run_id, who, 'new_cycle', {'reason': reason})
            db.execute('UPDATE refine_runs SET rewrites=0,calls=0 WHERE id=?', (run_id,))
            _touch(db, run, 'awaiting_revision')
        return self.status(token, run_id)

    def reserve_call(self, token, run_id, expected, stage, expected_context=None):
        require(stage in {'draft', 'review'}, "Unknown model stage")
        with transaction(self.root) as db:
            who, run = _access(db, token, run_id, expected, {'author'} if stage == 'draft' else {'reviewer'})
            context = _context(db, run)
            require(expected_context is None or digest(context) == expected_context, 'Evidence or policy changed; refresh before inference')
            if stage == 'draft':
                require(not any(q['state'] == 'open' for q in context['questions'].values()), "Owner decisions are pending; resolve them before another drafting call")
            else:
                _current(db, run)
            require(run['calls'] < context['policy']['policy']['max_model_calls'], "Model-call budget exhausted; operator decision required")
            call_id = _record(db, run_id, who, 'model_call_started', {'stage': stage, 'context_digest': digest(context)})
            db.execute('UPDATE refine_runs SET calls=calls+1 WHERE id=?', (run_id,))
            _touch(db, run, run['state'])
        return call_id, self.status(token, run_id)

    def finish_call(self, token, run_id, call_id, model, success, elapsed, metrics=None, provider='custom', prompt_digest=None):
        text(model, 'model identifier', 200)
        require(type(success) is bool and type(elapsed) in (float, int) and 0 <= elapsed < 3600, "Invalid model-call metadata")
        require(provider in {'ollama', 'local-openai', 'openai', 'anthropic', 'custom'}, 'Invalid provider metadata')
        allowed_metrics = {'total_duration', 'load_duration', 'prompt_eval_count', 'prompt_eval_cached_count', 'prompt_eval_duration', 'eval_count', 'eval_duration', 'input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens', 'prompt_tokens', 'completion_tokens', 'total_tokens', 'validation_milliseconds', 'provider_milliseconds'}
        metrics = {k: v for k, v in (metrics or {}).items() if k in allowed_metrics and type(v) is int and 0 <= v < 10**15}
        with transaction(self.root) as db:
            who, _ = _access(db, token, run_id)
            calls = [r for r in _records(db, run_id, 'model_call_started') if r['seq'] == call_id and r['actor'] == who['actor']]
            require(bool(calls), "Reserved model call not found for this actor")
            require(all(r['data']['call_id'] != call_id for r in _records(db, run_id, 'model_call_finished')), "Model-call result already recorded")
            _record(db, run_id, who, 'model_call_finished', {'call_id': call_id, 'model': model, 'provider': provider, 'prompt_digest': prompt_digest, 'succeeded': success, 'elapsed_seconds': elapsed, 'metrics': metrics or {}})

    def reject_preflight(self, token, run_id, expected, stage, reason):
        require(stage in {'draft', 'review'}, 'Unknown model stage')
        text(reason, 'preflight reason', 2000)
        with transaction(self.root) as db:
            who, _ = _access(db, token, run_id, expected, {'author'} if stage == 'draft' else {'reviewer'})
            _record(db, run_id, who, 'model_preflight_rejected', {'stage': stage, 'reason': reason, 'inference_reserved': False})

    def plan(self, token, run_id, profile='cucumber'):
        from .handoff import plan_files
        with transaction(self.root, write=False) as db:
            _, run = _access(db, token, run_id)
            require(run['state'] in {'awaiting_approval', 'approved'}, "No approvable handoff in this state")
            current, context, assessment = _ready(db, run)
            return plan_files(run, current, context, assessment, profile)

    def approve(self, token, run_id, expected, expected_digest, profile='cucumber', ttl=900):
        from .handoff import plan_files
        require(type(ttl) is int and 1 <= ttl <= 900, "Approval lifetime must be 1 to 900 seconds")
        with transaction(self.root) as db:
            who, run = _access(db, token, run_id, expected, {'operator'})
            require(run['state'] in {'awaiting_approval', 'approved'}, "Independent READY review required")
            current, context, assessment = _ready(db, run)
            plan = plan_files(run, current, context, assessment, profile)['plan']
            require(digest(plan) == expected_digest, "Inspect the exact current handoff before approving")
            now = time.time()
            approval_id = _record(db, run_id, who, 'approval', {'plan': plan, 'issued': now, 'expires': now + ttl})
            _touch(db, run, 'approved')
            return {'approval_id': approval_id, 'plan_digest': digest(plan)}

    def seal(self, token, run_id, approval_id):
        from .handoff import plan_files
        require(type(approval_id) is int, "Invalid approval ID")
        with transaction(self.root) as db:
            who, run = _access(db, token, run_id, roles={'operator'})
            approvals = [r for r in _records(db, run_id, 'approval') if r['seq'] == approval_id]
            require(bool(approvals) and approvals[0]['actor'] == who['actor'], "Approval not found for this operator")
            existing = db.execute('SELECT payload,digest FROM refine_exports WHERE approval_id=?', (approval_id,)).fetchone()
            if existing:
                value = json.loads(existing[0]); require(digest(value) == existing[1], "Export integrity failure")
                return value
            record = approvals[0]; approved = record['data']
            credential = db.execute('SELECT active FROM credentials WHERE id=?', (record['credential_id'],)).fetchone()
            require(credential is not None and credential[0] and approved['issued'] <= time.time() < approved['expires'], "Approval expired or its issuing capability was revoked")
            require(run['state'] == 'approved', "Approval was invalidated by a later operation")
            latest = _records(db, run_id, 'approval')[-1]
            require(latest['seq'] == approval_id, "Approval was superseded")
            current, context, assessment = _ready(db, run)
            bundle = plan_files(run, current, context, assessment, approved['plan']['profile'])
            require(bundle['plan'] == approved['plan'], "Approved handoff changed; inspect and approve again")
            value = {'kind': 'approved-developer-handoff', 'remote_published': False, 'approval': {'id': approval_id, 'actor': who['actor'], 'issued': approved['issued']}, **bundle}
            db.execute('INSERT INTO refine_exports VALUES(?,?,?,?)', (approval_id, run_id, canonical(value), digest(value)))
            _record(db, run_id, who, 'sealed', {'approval_id': approval_id, 'export_digest': digest(value)})
            _touch(db, run, 'exported')
            return value

    def exported(self, token, run_id, approval_id):
        require(type(approval_id) is int, "Invalid approval ID")
        with transaction(self.root, write=False) as db:
            _access(db, token, run_id)
            row = db.execute('SELECT payload,digest FROM refine_exports WHERE run_id=? AND approval_id=?', (run_id, approval_id)).fetchone()
            require(row is not None, "No sealed export exists")
            value = json.loads(row[0])
            require(digest(value) == row[1], "Export integrity failure")
            return value

    def status(self, token, run_id):
        with transaction(self.root, write=False) as db:
            who, run = _access(db, token, run_id)
            context = _context(db, run)
            drafts = _records(db, run_id, 'draft'); reviews = _records(db, run_id, 'review')
            current = drafts[-1] if drafts else None
            checked = checks.check(current['data']['draft'], context['sources'], context['policy']['policy']) if current else None
            stale = bool(current and (current['data']['context_digest'] != digest(context) or current['data']['engine_digest'] != engine_digest()))
            ordered = sorted((q for q in context['questions'].values() if q['state'] == 'open'), key=lambda q: (-q['impact'], q['id']))
            return {'actor': {'name': who['actor'], 'role': who['role']}, 'run': run, 'context': context, 'context_digest': digest(context), 'draft': current['data']['draft'] if current else None, 'draft_digest': digest(current['data']['draft']) if current else None, 'draft_record': current['seq'] if current else None, 'stale': stale, 'checks': checked, 'review': reviews[-1]['data'] if reviews and current and reviews[-1]['data']['draft_record'] == current['seq'] and not stale else None, 'next_question': ordered[0] if ordered else None, 'open_questions': ordered, 'model_calls': [r['data'] for r in _records(db, run_id, 'model_call_finished')][-12:], 'events': [{'id': r['seq'], 'kind': r['kind'], 'actor': r['actor'], 'digest': r['digest']} for r in _records(db, run_id)]}

    def list_runs(self, token):
        with transaction(self.root, write=False) as db:
            _schema(db); who = authenticate(db, token)
            query = 'SELECT * FROM refine_runs'; args = ()
            if who['role'] == 'author':
                query += ' WHERE owner=?'; args = (who['actor'],)
            return [dict(r) for r in db.execute(query + ' ORDER BY created DESC', args)]

    def verify(self, token, run_id):
        with transaction(self.root, write=False) as db:
            _access(db, token, run_id)
            previous = ''
            for record in _records(db, run_id):
                body = {key: record[key] for key in ('run_id', 'kind', 'actor', 'credential_id', 'digest', 'previous_hash', 'created')}
                require(record['previous_hash'] == previous and digest(body) == record['hash'], "Refinement audit chain failed integrity verification")
                previous = record['hash']
            for row in db.execute('SELECT payload,digest FROM refine_exports WHERE run_id=?', (run_id,)):
                require(digest(json.loads(row[0])) == row[1], "Export integrity verification failed")
            return {'valid': True, 'head_hash': previous, 'tamper_proof_against_os_owner': False}
