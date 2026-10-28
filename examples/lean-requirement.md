# Fictional lean requirement examples

These examples are invented personal projects, with no real Jira or Confluence
connection. A real run replaces the evidence placeholder with its verified URL.

## Behavioral payload

Review evidence: {logbook_url}

### Export my personal reading list
As a reader, I want a CSV export so that I can keep a copy of my saved books.

Scope: export the current user's complete list, in its displayed order, using
UTF-8 CSV with a header row (`title`, `author`) and standard CSV quoting. The
export preserves the saved list. Import and filtering are out of scope.

Acceptance criteria: see the three scenarios in `behavioral.feature`. In an actual
Jira payload those scenarios are inlined here; this is a repository example.

## Non-behavioral payload

Review evidence: {logbook_url}

### Compare storage options for a personal reading list
Decide whether a local JSON file or SQLite better meets a single-user reading
list's storage needs. No implementation or hosted service is in scope.

- [ ] Compare JSON and SQLite on schema changes, backup/restore, and implementation effort in a decision note.
- [ ] Demonstrate saving and reloading the same three fictional books with each option; record exact commands and results.
- [ ] Recommend one option with rationale and unresolved tradeoffs in the decision note, ready for the owner to approve.

## Review notes (run docs only — not posted)
These examples have fictional owner-provided requirements. A real run records its
verified sources with title, section, last-modified date, and locator here. Keep
rationale and source tables in this section. Never invent a requirement or a
measurement to achieve readiness.
