"""One approved Gherkin text for developers and test management. No remote writes."""
from __future__ import annotations
import hashlib
import io
import json
import zipfile

from ..guardrails import canonical, digest
from .contracts import KINDS, require

PROFILES = {'cucumber', 'xray-cloud', 'xray-server-dc'}


def plan_files(run, current, context, assessed, profile):
    require(profile in PROFILES, "Choose cucumber, xray-cloud or xray-server-dc explicitly")
    value = current['data']['draft']
    lines = ['# ' + value['title'], '', 'Approved acceptance criteria are in acceptance.feature. They are not regenerated for testing.', '']
    for kind in ('problem', 'value', 'scope', 'exclusion', 'definition', 'rule', 'constraint', 'dependency'):
        statements = [s for s in value['statements'] if s['kind'] == kind]
        if statements:
            lines += ['## ' + kind.title(), '']
        for statement in statements:
            lines += ['### ' + statement['id'], '', statement['text'], '', 'Sources: ' + ', '.join(c['source_id'] for c in statement['citations']), '']
    trace = {'statements': value['statements'], 'scenario_mappings': value['scenarios'], 'coverage': value['coverage'], 'draft_digest': digest(value)}
    files = {
        'requirement.md': '\n'.join(lines),
        # Preserve even trailing newlines and CRLF; hash and export the approved bytes.
        'acceptance.feature': value['feature'],
        'traceability.json': canonical(trace) + '\n',
        'sources.json': canonical(context) + '\n',
        'quality-review.json': canonical(assessed['data']) + '\n',
        'IMPORT-NOTES.txt': 'Profile: ' + profile + '\nLocal export only; no tests were created in a tracker.\n'
            'The feature is byte-identical to the approved acceptance criteria.\n'
            'Import only acceptance.feature into test management, not this evidence-bearing ZIP.\n'
            'No Jira project key, requirement link or existing Test key is inferred.\n'
            'Validate import into your selected Xray edition and project before operational use.\n'
            'Repeated imports can create or update tests; local sealing is not remote deduplication.\n'
            'A feature file specifies tests; executable automation still needs step definitions.\n',
    }
    hashes = {name: hashlib.sha256(body.encode('utf-8')).hexdigest() for name, body in files.items()}
    plan = {'schema_version': 1, 'action': 'seal_developer_handoff', 'profile': profile, 'run_id': run['id'], 'revision': current['data']['revision'], 'draft_digest': digest(value), 'context_digest': digest(context), 'review_digest': assessed['digest'], 'engine_digest': current['data']['engine_digest'], 'files': hashes}
    return {'plan': plan, 'plan_digest': digest(plan), 'files': files}


def archive(bundle: dict) -> bytes:
    require(bundle.get('kind') == 'approved-developer-handoff' and bundle.get('remote_published') is False, "Only a sealed handoff can be packaged")
    require(set(bundle['files']) == set(bundle['plan']['files']), "File manifest differs from the approved plan")
    for name, body in bundle['files'].items():
        require('/' not in name and '\\' not in name and name not in {'.', '..'}, "Unsafe export filename")
        require(hashlib.sha256(body.encode()).hexdigest() == bundle['plan']['files'][name], "Approved file hash mismatch")
    require(digest(bundle['plan']) == bundle['plan_digest'], "Plan integrity failure")
    files = {**bundle['files'], 'manifest.json': canonical({k: v for k, v in bundle.items() if k != 'files'}) + '\n'}
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name, body in sorted(files.items()):
            item = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o600 << 16
            z.writestr(item, body.encode())
    return out.getvalue()
