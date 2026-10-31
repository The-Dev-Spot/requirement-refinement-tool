# Evaluation Report — {story_id}   (replace-in-place)

Scored against `rubric/definition-of-ready.md`. Story type: {behavioral | non-behavioral}.

## Deterministic checks (skill-gherkin-lint)
| Check | Result | Offending text / note |
|-------|--------|-----------------------|
| L1 Gherkin parses | {pass/WARN/FAIL/n-a} | |
| L2 Tag syntax | {...} | |
| L3 Vague terms | {...} | |
| L4 Declarative steps | {...} | |
| L5 @risk resolves | {...} | |
| L6 Provenance format | {...} | |
| L7 Open-question syntax | {...} | |
| L8 Step-catalog preference | {...} | |
| L9 AC budget (max 8) | {...} | {count} |
| L10 Converted payload size | {...} | {description chars; longest AC item} |

Unavailable checks are `NOT_RUN`; include checker identity and evidence.

`hard_fail`: {true|false}   (if true, GATE = FAIL and semantic scoring is skipped)

## Dimensions (skill-story-eval)
| Dim | Result | Evidence (quote / citation) |
|-----|--------|-----------------------------|
| D1 Cold-read independence | {...} | |
| D2 Story shape & value | {...} | |
| D3 AC present & format-appropriate | {...} | |
| D4 Testable & precise | {...} | |
| D5 Risk coverage | {...} | |
| D6 Provenance & no invented reqs | {...} | |
| D7 Scope & sizing | {...} | |
| D8 Dependencies & assumptions | {...} | |
| D9 Data & interface contracts | {...} | |
| D10 Non-functional & compliance | {...} | |

## GATE: {PASS | WARN | FAIL | BLOCKED / NOT_VERIFIED}
Reasons: {the specific executed checks/dimensions that set the gate}

Checker version/source hash: {exact validator + sha256 or NOT_RUN}
Project DoR/risk policy adoption and revision: {source or NOT_VERIFIED}
Independent reviewer run evidence: {separate authenticated invocation reference or NOT_VERIFIED}
NOTE: Mechanical PASS does not imply READY or executed regression tests.

## Open questions raised
- # OPEN QUESTION -> PO: {...}
