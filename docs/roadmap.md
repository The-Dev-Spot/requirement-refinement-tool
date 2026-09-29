# Personal Clarity roadmap

## P0 — trusted runtime and publication boundary

Implement durable run/revision state, authenticated owner decisions and a
separate scoped publisher. Approval must bind run, artifact revision, source
revision, exact target, actions and payload hashes. Reject stale approvals; claim
idempotency atomically; reconcile timeouts; prohibit hidden field/label writes.
Acceptance: concurrent duplicate submissions, forged approvals, changed evidence,
partial failure and unauthorized field writes fail safely in integration tests.
Keep live writes disabled until this gate is met. No deployment is part of v0.1.

## P1 — executable quality and adversarial evaluation

Implement a parser-backed Gherkin/checklist linter and the remaining L1-L8 rules.
Separate grammar validation from stylistic narrative-order policy. Build a
versioned synthetic gold set spanning behavioral, business, research, API and
regulated scenarios, contradictions, inaccessible sources and injected commands.
Acceptance: deterministic rules have positive/negative fixtures; semantic
judgments are compared with human labels; unsupported assertions and missing
blockers are measured. No model evaluates only its own rewrite.

## P1 — provider-neutral integrations and pipeline handoff

Define typed requirement, evidence, question, evaluation and publication schemas.
Start with local Markdown import/export and a read-only Linear adapter; add Jira
and GitHub by demand. Resolve permissions, pagination, custom fields, timeouts,
rate limits and source revision identifiers explicitly.
Acceptance: contract tests for each adapter; no provider constants in the rubric;
versioned approved handoff includes source coverage, blockers, artifact digest
and decision trail. No automatic downstream build of NOT READY requirements.

## P1 — durable evidence, resume and traceability

Use immutable per-run revisions and stable question IDs. Source-to-AC coverage
must survive proposal merges, owner replies and intake-to-created-issue mapping.
Acceptance: interrupted runs resume without duplicate artifacts or writes;
contradictory owner replies remain visible; hashes detect changed evidence;
retention deletion stays disabled until backup and restore tests pass.

## P2 — focused user experience and measurable improvement

Build a lightweight local workbench before a multi-tenant service: intake,
source panel, before/after diff, question queue, rubric rationale and exact
publication preview. Show cost and elapsed time, with explicit waiting states.
Acceptance: a new user can inspect why a requirement is blocked and approve only
specific reviewed changes. Measure time to approved handoff, owner edit burden,
unsupported-claim rate and missed blockers; track question quality, not just count.

## P2 — portability and maintainability

Add host-specific smoke tests, native subagent/skill registrations where needed,
versioned prompt bundles and dependency/security scanning. Separate maintainer
coding mode from requirement-analysis mode. Keep model selection configurable;
introduce more infrastructure only after measured benefit.
