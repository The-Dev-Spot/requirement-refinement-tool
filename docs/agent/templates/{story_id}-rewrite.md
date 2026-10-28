# Rewrite — {story_id} (write-once)

## Jira payload

Review evidence: {logbook_url}

### {title: observable outcome}
As a {role}, I want {capability}, so that {benefit}.

### Scope and constraints
{Only facts needed to build and verify: affected surface, confirmed values,
 boundaries, decisions, and blocking dependencies. Explain essential terms inline.}

### Acceptance criteria
{Behavioral: fenced Gherkin Feature with 3–6 declarative scenarios, max 8;
 Scenario Outline counts once. Non-behavioral: 3–6 measurable checklist items,
 max 8, aim at ≤250 characters each. Choose one format; remove this instruction.}

# OPEN QUESTION -> PO: {only an unresolved gap; omit when none}

## Review notes (run docs only — not posted)

### Sources and provenance
| Claim / AC | Source title and section | Last modified | Locator |
|---|---|---|---|
| {claim} | {source} | {verified date, or explicitly unknown} | {URL/path} |

### What changed and why
- {finding and concise rationale; risk mapping and precedent live here}

### Residual gate and measurements
{PASS/WARN/FAIL/NOT_RUN; open questions, AC count, converted-description length,
 longest checklist item, and executed checker identity. No invented result.}

The Jira payload alone must pass the cold-read test. Target ≤8,000 description
characters after conversion; WARN >10,000, FAIL >20,000. Split if essential build
facts do not fit. Never put a source table, glossary, or review rationale in the
payload. This section and all template instructions are excluded from Jira.
