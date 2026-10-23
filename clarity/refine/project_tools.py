"""Explicit project glossary operations on the existing append-only record store.

No new database schema, model permissions or remote integration. A requirement
uses a selected glossary revision as an ordinary source, not a live global prompt.
"""
from __future__ import annotations

from ..guardrails import canonical, digest, identifier
from ..storage import transaction
from .contracts import detached, fields, require, source_record, text
from .controller import Controller, _access, _context, _record, _records, _schema, _touch
from .identity import authenticate


def validate_glossary(value: dict) -> dict:
    value = detached(value)
    fields(value, {'schema_version', 'terms', 'reason'}, 'project glossary')
    require(type(value['schema_version']) is int and value['schema_version'] == 1, 'Unsupported glossary version')
    require(len(text(value['reason'], 'approval rationale', 4000).strip()) >= 20, 'Explain why these definitions apply')
    terms = value['terms']
    require(isinstance(terms, list) and 1 <= len(terms) <= 100, 'Provide 1 to 100 glossary terms')
    seen_ids, seen_names = set(), set()
    for item in terms:
        fields(item, {'id', 'term', 'definition', 'aliases'}, 'glossary term')
        identifier(item['id'])
        require(item['id'] not in seen_ids, 'Duplicate glossary term ID')
        seen_ids.add(item['id'])
        text(item['definition'], 'term definition', 4000)
        aliases = item['aliases']
        require(isinstance(aliases, list) and len(aliases) <= 20, 'Invalid term aliases')
        for name in [item['term'], *aliases]:
            text(name, 'term or alias', 200)
            require('\n' not in name and '\r' not in name, 'Term names must be one line')
            normalized = ' '.join(name.casefold().split())
            require(normalized not in seen_names, 'Term names and aliases must be unambiguous')
            seen_names.add(normalized)
    require(len(canonical(value).encode('utf-8')) <= 80000, 'Glossary exceeds source budget')
    return value


def _selected(db, project, record=None):
    candidates = [r for r in _records(db, None, 'project_glossary') if r['data']['project'] == project]
    if record is not None:
        candidates = [r for r in candidates if r['seq'] == record]
    return candidates[-1] if candidates else None


class ProjectTools:
    def __init__(self, root):
        self.root = root

    def glossary(self, token, project, record=None):
        identifier(project)
        require(record is None or type(record) is int and record > 0, 'Invalid glossary record')
        with transaction(self.root, write=False) as db:
            _schema(db)
            authenticate(db, token)
            selected = _selected(db, project, record)
            require(record is None or selected is not None, 'Glossary revision not found in this project')
            if selected is None:
                return {'project': project, 'record': 0, 'glossary': None}
            return {'project': project, 'record': selected['seq'], 'digest': selected['digest'],
                    'approved_by': selected['actor'], 'glossary': selected['data']['glossary']}

    def approve_glossary(self, token, project, value, expected_record):
        identifier(project)
        value = validate_glossary(value)
        require(type(expected_record) is int and expected_record >= 0, 'Supply the last displayed glossary record')
        with transaction(self.root) as db:
            _schema(db)
            who = authenticate(db, token, {'operator'})
            previous = _selected(db, project)
            require((previous['seq'] if previous else 0) == expected_record, 'Glossary changed; inspect it again')
            record = _record(db, None, who, 'project_glossary', {'project': project, 'glossary': value})
        return self.glossary(token, project, record)

    def attach_glossary(self, token, run_id, expected, record, expected_digest, replace_source_id=None):
        require(type(record) is int and record > 0, 'Select an approved glossary record')
        with transaction(self.root) as db:
            who, run = _access(db, token, run_id, expected, {'operator'})
            selected = _selected(db, run['project'], record)
            require(selected is not None and selected['digest'] == expected_digest, 'Selected glossary revision is absent or changed')
            context = _context(db, run)
            source_id = 'GLOSSARY-' + str(record)
            require(source_id not in context['sources'], 'This glossary revision is already selected')
            if replace_source_id is not None:
                old = context['sources'].get(replace_source_id)
                require(old is not None and old['kind'] == 'reference'
                        and old['locator'].startswith('local:glossary:' + run['project'] + ':'),
                        'Select a current glossary source to replace')
            body = canonical(selected['data']['glossary'])
            sources = [s for sid, s in context['sources'].items() if sid != replace_source_id]
            require(len(sources) < 21 and sum(len(s['text'].encode()) for s in sources) + len(body.encode()) <= 300000,
                    'Selected source budget exceeded')
            source = source_record(source_id, 'Approved project glossary revision ' + str(record), body,
                                   'local:glossary:' + run['project'] + ':' + str(record), 'reference',
                                   'operator:' + who['actor'] + ':selected-glossary:' + str(record))
            _record(db, run_id, who, 'source', source)
            if replace_source_id is not None:
                _record(db, run_id, who, 'source_superseded', {'old_id': replace_source_id, 'new_id': source_id})
            _touch(db, run, 'awaiting_revision')
        return Controller(self.root).status(token, run_id)
