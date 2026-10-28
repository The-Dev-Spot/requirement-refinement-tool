"""Compact developer text; complete evidence stays in the sealed audit bundle."""
from __future__ import annotations

TARGET_SCENARIOS = (3, 6)
MAX_SCENARIOS = 8
TARGET_CHARACTERS = 8_000
WARN_CHARACTERS = 10_000
MAX_CHARACTERS = 20_000


def requirement_text(value: dict) -> str:
    """Render every approved statement verbatim, without audit-only scaffolding.

    This is a presentation change, never summarization or truncation. Stable IDs,
    source passages, coverage and reviewer reasoning remain in traceability.json,
    sources.json and quality-review.json. Acceptance lives in the exact feature.
    """
    lines = ['# ' + value['title'], '',
             'Acceptance criteria: [acceptance.feature](acceptance.feature).', '']

    def section(title, kinds, labels=None):
        statements = [s for kind in kinds for s in value['statements'] if s['kind'] == kind]
        if not statements:
            return
        lines.extend(['## ' + title, ''])
        for statement in statements:
            prefix = (labels or {}).get(statement['kind'], '')
            # Keep multiline tables/paragraphs intact, rather than nesting or
            # flattening build-relevant text into a synthesized bullet.
            lines.extend([prefix + statement['text'], ''])

    section('Objective', ('problem', 'value'))
    section('Scope', ('scope', 'exclusion'), {'scope': '**In scope:** ', 'exclusion': '**Out of scope:** '})
    section('Build details', ('definition', 'rule', 'constraint'))
    section('Dependencies', ('dependency',))
    return '\n'.join(lines)


def payload_metrics(value: dict, scenario_index: dict | None) -> dict:
    """Count both delivery files, so moving text into Gherkin cannot hide size.

    Scenario Outlines count once; their compiled Examples still retain the
    independent parser limits. Characters are Unicode code points in UTF-8 text,
    not byte counts or a Jira-markup estimate: this product exports local files.
    """
    requirement_chars = len(requirement_text(value))
    feature_chars = len(value['feature'])
    return {'scenario_count': len(scenario_index['scenarios']) if scenario_index else None,
            'requirement_characters': requirement_chars,
            'feature_characters': feature_chars,
            'delivery_characters': requirement_chars + feature_chars,
            'target_scenarios': list(TARGET_SCENARIOS), 'max_scenarios': MAX_SCENARIOS,
            'target_characters': TARGET_CHARACTERS, 'warn_characters': WARN_CHARACTERS,
            'max_characters': MAX_CHARACTERS}
