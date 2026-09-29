# Standalone Clarity roadmap

## Product decision

Clarity is a standalone product. No development-pipeline connection, automatic
story dispatch or integration-dependent architecture is part of this phase.
The current deliverable is a local-first refinement and review controller.

## Delivered in v0.2

Durable SQLite runs and immutable revisions; authenticated local role capabilities;
independent digest-bound reviews; application-computed L1-L8 rules; stable owner
questions; mandatory post-answer revision/review; exact expiring approvals;
atomic idempotent local artifact sealing; explicit backup/restore; corruption
checks; sticky quarantine; a three-rewrite budget; Markdown import; bounded
read-only Linear import; a static review workbench; adversarial/concurrency
regressions and synthetic rule benchmarks. See the hardening record for limits.

## Next standalone product decisions — not implemented

**Operator experience and host integration.** Validate the preserved ten-role
workflow with the actual editor/model host. Decide whether to add a small local
server and real interactive workbench. Acceptance: server-side authentication,
per-action authorization, CSRF/origin controls, separate controller identity,
usable approval preview, and no agent access to operator credentials. The current
static HTML view deliberately cannot approve anything.

**Semantic quality benchmark.** Build a human-labelled, versioned corpus of
behavioral, infrastructure, research and domain-regulated requirements. Measure
unsupported claims, missed blockers, useful questions, owner corrections, time
and cost. Compare independent evaluators rather than only model self-scores.
The shipped 13-case rule suite is synthetic regression coverage, not this study.

**Live read integration validation.** Test the Linear reader using a separately
provided read-only key and chosen team/project. Validate real schema, pagination,
permission errors, source freshness, comments edited during retrieval and resource
limits. Add other providers only when required for the standalone product.

**Third-party publication.** Keep it disabled until explicitly requested. A future
writer requires authenticated exact-action approval, fresh remote revision checks,
field allowlists, persistent operation IDs, timeout reconciliation and real
integration tests. Local exactly-once sealing does not promise remote exactly-once
creation. No remote API writer has been added merely to check a roadmap box.

**Packaging and operation.** Validate secure Windows ACL support before enabling
it, package policy resources for distribution, add an independent secret scanner,
measure larger-workspace behavior, and decide on encrypted backups and retention.
No automatic deletion until recovery and operator selection are demonstrably safe.

These are subsequent standalone improvements, not authorization to expand scope
or integrate with another product now.
