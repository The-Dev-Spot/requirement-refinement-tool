import copy
import json
from pathlib import Path
from clarity.refine.contracts import SEMANTIC_CHECKS
from clarity.guardrails import digest

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = json.loads((ROOT / 'examples/refinement-reference.json').read_text())


def sample(source=None):
    value = copy.deepcopy(REFERENCE['draft'])
    if source:
        for s in value['statements']:
            for c in s['citations']:
                c['source_digest'] = source['digest']
    return value


def assessment(value):
    note = {'status': 'PASS', 'rationale': 'Synthetic reviewer fixture: the specified behavior matches the confirmed source and observable outcomes.'}
    return {'draft_digest': digest(value), 'checks': {k: copy.deepcopy(note) for k in SEMANTIC_CHECKS}, 'statement_support': {s['id']: copy.deepcopy(note) for s in value['statements']}, 'scenario_fidelity': {s['id']: copy.deepcopy(note) for s in value['scenarios']}, 'warning_resolutions': {}, 'ambiguities': []}
