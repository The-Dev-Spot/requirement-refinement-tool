"""Provider-neutral JSON Schema contracts; business validation stays in contracts.py."""
from .contracts import CATEGORIES, KINDS, SEMANTIC_CHECKS


def obj(**properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


def arr(item):
    return {'type': 'array', 'items': item}


STRING = {'type': 'string'}
NULLABLE = {'type': ['string', 'null']}
CHECK = obj(status={'type': 'string', 'enum': ['PASS', 'FAIL', 'NOT_RUN']}, rationale=STRING)
CITATION = obj(source_id=STRING, source_digest=STRING, quote=STRING)
DRAFT = obj(
    version={'type': 'integer', 'enum': [1]}, title=STRING,
    statements=arr(obj(id=STRING, kind={'type': 'string', 'enum': sorted(KINDS)}, text=STRING, citations=arr(CITATION))),
    feature=STRING,
    scenarios=arr(obj(id=STRING, statement_ids=arr(STRING), category={'type': 'string', 'enum': list(CATEGORIES)})),
    coverage=arr(obj(statement_id=STRING, category={'type': 'string', 'enum': list(CATEGORIES)}, scenario_ids=arr(STRING), not_applicable_reason=NULLABLE)),
    proposals=arr(STRING))
QUESTIONS = arr(obj(id=STRING, text=STRING, why=STRING, impact={'type': 'integer'},
                    prerequisites=arr(STRING)))


def changes(item, removal=STRING):
    return obj(upsert=arr(item), remove=arr(removal))


def response_schema(stage, status):
    if stage == 'intake':
        return obj(questions=QUESTIONS, ready_to_draft={'type': 'boolean'})
    if stage == 'draft':
        return obj(questions=QUESTIONS, draft={'anyOf': [DRAFT, {'type': 'null'}]})
    if stage == 'revise':
        props = DRAFT['properties']
        # Keep the schema stable across text edits. The task supplies the digest;
        # controller validation enforces its exact value before applying output.
        patch = obj(base_draft_digest=STRING, title=NULLABLE,
                    statements=changes(props['statements']['items']), feature=NULLABLE,
                    scenarios=changes(props['scenarios']['items']),
                    coverage=changes(props['coverage']['items'], obj(statement_id=STRING, category={'type': 'string', 'enum': list(CATEGORIES)})),
                    proposals={'anyOf': [props['proposals'], {'type': 'null'}]})
        return obj(questions=QUESTIONS, revision={'anyOf': [patch, {'type': 'null'}]})
    value = status['draft']
    warnings = [f['id'] for f in status['checks']['findings'] if f['severity'] == 'warning']
    # A fixed property set works with strict provider schemas. Null means no
    # disposition; the worker removes it before normal controller validation.
    warning_schema = obj(**{k: NULLABLE for k in warnings})
    return obj(draft_digest=STRING,
               checks=obj(**{k: CHECK for k in SEMANTIC_CHECKS}),
               statement_support=obj(**{s['id']: CHECK for s in value['statements']}),
               scenario_fidelity=obj(**{s['id']: CHECK for s in value['scenarios']}),
               warning_resolutions=warning_schema,
               ambiguities=arr(obj(statement_ids=arr(STRING), interpretation_a=STRING, interpretation_b=STRING, material_difference=STRING)))
