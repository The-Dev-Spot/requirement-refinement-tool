# Architecture

The installed `clarity` CLI owns setup, diagnostics, encrypted backups and local
startup. `clarity.refine.Controller` owns the requirement workflow. Server-rendered
pages expose explicit role-specific actions; providers and assistants cannot approve.

| Component | Responsibility |
| --- | --- |
| `storage.py` | Private POSIX SQLite transactions; read-only queries use deferred transactions |
| `refine/controller.py` | Immutable source/decision/draft/review events, optimistic versions and exact approval/sealing |
| `workspace.py` | Versioned source/model configuration and encrypted credential references |
| `refine/web.py`, `refine/views.py`, `assets/` | Loopback HTTP boundary, CSRF/session handling and escaped accessible forms |
| `host_bridge.py` | Scoped author/reviewer stdio MCP tools for existing coding assistants |
| `jobs.py` | Two bounded background inference slots, durable status and cooperative cancellation |
| `refine/worker.py`, `connections.py`, `local_model.py` | Explicit model/source transports, bounded packets and strict output validation |
| `refine/checks.py`, `schemas.py` | Official Gherkin parsing, multiline outline checks, coverage, provenance and provider JSON schemas |
| `backup.py`, `backup_crypto.py` | Consistent versioned snapshots and authenticated passphrase encryption |
| `evaluation.py`, `handoff_check.py` | Grouped repeated trials and read-only Xray pilot receipt checks |

## Requirement lifecycle

Capture can be incomplete. Only a reviewed complete revision can reach approval.
Sources, decisions, policy and executable quality resources bind the current draft.
Changed context invalidates old review/approval. Questions retain stable IDs;
source replacement preserves earlier evidence in the audit history.

Inference preflight validates packet size and credential-like literals before
reserving an attempt. The controller rechecks the context atomically. Provider
output is applied only to the reserved version and context; cancellation is
serialized with result recording. A restarted application marks active jobs
interrupted and requires an explicit retry.

Independent review is digest-bound and cannot come from the author identity.
The operator's short-lived approval binds the exact handoff plan and file hashes.
Sealing and repeat retrieval use the same immutable stored bundle. Export never
performs remote publication or creates executable step definitions.

## Storage and distribution

The base database and additive refinement/configuration namespaces have explicit
schema versions. Backups include all supported non-secret namespaces. Unknown or
partial namespaces fail closed. Read transactions do not reserve the writer lock;
no speculative cache is added for a small local workload.

Wheels contain the human quality contracts needed to compute the engine digest,
so installed operation does not depend on a repository checkout. Canonical copies
are included by `build_support.py`; changes to quality code/contracts invalidate
old unsealed revisions. Assets load from the installed package without a CDN.

The old `runtime.py` snapshot API remains for compatibility. Its checklist exports
are separate from the current Gherkin handoff standard.
