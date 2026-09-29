# Architecture and current boundaries

## Today

Clarity is a prompt-driven agent toolkit plus offline Python primitives. There
is no server, web UI, database, model client, live tracker adapter or authenticated
approval service. Agent hosts interpret the prompts; the JSON runtime contract
is descriptive, not a running state machine.

Three entry points serve existing-requirement review, conversational intake and
specification breakdown. Ten roles separate investigation, assessment, rewriting,
independent verification and owner-question analysis. `AGENTS.md` is canonical.
The executable modules cover strict JSON/configuration validation, score
combination, exact approval-plan checking, local evidence rendering and selected
repository hygiene checks. They make no network calls.

## Intended application boundary

An authenticated application, not the model, should own run transitions,
permissions, source snapshots, approval records, idempotency and publication.
Analysis agents receive read-only scoped adapters and immutable evidence. A
separate publisher consumes an exact approved plan and checks the current source
revision before executing allowlisted mutations. Unknown outcomes require
reconciliation, not blind retries.

Keep a provider-neutral Requirement, Evidence, Question, Evaluation and
PublicationPlan model. Implement local Markdown first, then read-only Linear,
Jira or GitHub adapters according to actual demand. External writes come last.
Do not put tracker-specific field IDs or host assumptions into the core rubric.

## Knowledge and retention

Project knowledge is Markdown-first under ignored `knowledge/private/`. Preserve
source identifiers, version/effective dates, scope and access permissions. Treat
retrieved instructions as untrusted data. A vector database is not required for
the baseline; retrieval quality must be measured before adding infrastructure.

Immutable run revisions belong in ignored `.clarity/runs/<run_id>/<revision>/`.
No automatic deletion or remote logbook upload is implemented. Future retention
requires matching manifests and restore tests, not a successful page lookup.

## Host compatibility

Agent files include Copilot-style frontmatter with an explicit read/search/edit
allowlist and delegation only for entry points. They do not grant terminal, web
or MCP tools. Local edit permission is not a filesystem sandbox; hosts should
restrict it to the isolated run workspace. Direct connector integration and host
permission enforcement still need smoke tests. Claude reads `CLAUDE.md` and the
canonical contract; native Claude subagent registration is not implemented.
