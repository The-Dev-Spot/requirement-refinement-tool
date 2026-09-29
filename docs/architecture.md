# Standalone architecture

Clarity's fixed output is an evidence-backed requirement with canonical Gherkin
acceptance criteria. Input expertise changes the assistance, not the quality bar.

## Product path (v0.3)

`clarity.refine.Controller` owns raw briefs, selected evidence, source applicability,
questions, confirmed answers, immutable drafts, independent reviews, exact approvals
and sealed developer handoffs. `contracts.py` separates incomplete input from the
complete output. `checks.py` validates source references, quotations, trusted policy,
Gherkin syntax/compiler results, traceability and coverage. Semantic truth is still
assessed independently; no heuristic claims to prove it.

The controller adds `refine_meta`, `refine_runs`, `refine_records`, `refine_exports`
to the existing private SQLite workspace through an explicit versioned bootstrap.
It preserves the base schema and existing records. New runs are not visible to
the legacy snapshot API, so a legacy approval cannot publish a new draft. Shared
capabilities retain fixed author/reviewer/operator roles. Authors can access only
their own briefs; reviewers/operators span this single trusted workspace.

Records are immutable and hash-chained; optimistic versions and immediate SQLite
transactions prevent stale writes. External inference takes place outside database
transactions. A model attempt is reserved before calling and never retried silently.
Completed outputs are rejected if decisions/source versions changed while waiting.

## Reasoning and models

The optional `worker.py` runner makes two explicit calls: evidence-based interviewing
or drafting, then fresh independent review. It does not dispatch all ten role profiles.
Drafting returns either bounded questions or a strict draft; review returns complete
statement/scenario findings and semantic checks. Outputs cannot grant authority,
change policy, choose tools, approve or publish. An operator chooses the model(s)
and authorizes selected data for that deployment. A fresh reviewer context receives
neither the writer's self-score nor a previous review score.

The implemented transport targets Ollama on 127.0.0.1 only, without proxies,
redirects or tool calls. Model names are explicit. Loopback does not guarantee
local inference: verify cloud-backed-model settings and data handling. There are
size/call/output budgets and socket timeouts, not an isolated inference sandbox.
A crash leaves a visible reserved attempt; a human chooses whether to retry.

## Workbench

`python -m clarity.refine --state ... serve` runs a local server-rendered UI.
It supports plain-language input, selected-source capture, targeted questions,
role-specific drafting/review/approval actions, evidence, diffs and coverage.
No JavaScript, remote assets, credential-bearing model requests or administrative
provisioning endpoint is supplied. Host/origin checks, CSRF tokens, strict forms,
HttpOnly SameSite cookies, escaped content and no-store responses protect this
loopback use case. Do not proxy it onto the internet.

## Handoff and recovery

The operator approves exact generated file hashes, source/context/review/engine
versions and an explicit export profile. The Gherkin file is copied byte-for-byte
from the approved draft. SQLite atomically records approval consumption and sealed
files; repeated sealing retrieves the existing result. File retrieval is separate
and retryable. No remote test creation or execution is implied.

The backup API supports the old v1 envelope and a v2 envelope including refinement
records. Restore uses a new private destination, validates hashes/chains and disables
all old keys. Pending approvals require a new independent review/approval. Previously
sealed exports remain historical evidence. Encryption and automatic pruning are absent.

## Compatibility and boundaries

The v0.2 controller, read-only Linear adapter and old helpers remain available.
Their checklist artifacts are legacy exports, not v0.3 quality-approved handoffs.
This is a standalone application, not a development-pipeline front end. No
enterprise identity provider, public API, multi-tenant access control, guaranteed
prompt-injection detection, source-system authority verification or live Xray
publisher is implemented. Use human-reviewed evaluations before quality claims.
