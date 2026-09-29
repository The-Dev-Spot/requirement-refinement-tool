# Standalone architecture — v0.2

Clarity is independent of any development-agent pipeline. The product boundary
is requirement intake/refinement, evidence-backed review, operator decisions,
and an approved local artifact. No downstream integration is included.

## Controller and trust boundary

`clarity.runtime.Workflow` owns durable transitions through SQLite. Public methods
authenticate a role-scoped capability inside the same transaction as the requested
operation. The CLI is an operator-facing wrapper over those methods, not a server.
Credential provisioning belongs to the OS owner. The database stores only hashes
of random capability keys; actual secrets are written to selected private files.

The author owns its run revisions. A separate fixed-role reviewer submits
semantic assessments bound to the current snapshot digest. The application runs
machine checks independently. Only an operator can answer questions, release
quarantine, extend a rewrite cycle, reject, approve or seal an export.

State and capability files must be outside untrusted agent access. An arbitrary
process running as the controller's OS owner can defeat these checks; no claim of
filesystem sandboxing or enterprise identity verification is made. There is no
network API or multi-tenant authorization model in this release.

## Storage and consistency

SQLite transactions use explicit BEGIN IMMEDIATE, foreign keys and FULL
synchronous durability. Revision, review, event and export records have no-update/
no-delete triggers. Operations require optimistic run versions. Transactions
roll back on failure; a stale caller must refresh, not silently overwrite state.

The controller states are awaiting_review, awaiting_revision, awaiting_po,
awaiting_approval, approved, quarantined, exported and rejected. Waiting is not
completion. Source and run identity are stable; new evidence produces revisions.
A three-rewrite cycle limit requires a recorded operator extension when exhausted.

Every event carries the previous event hash. Artifact hashes and chain validation
detect accidental corruption, not malicious rewriting by the database owner.
Backups use a consistent transaction and exclude authentication secrets/hashes.
Restore verifies the retained digest and artifacts, uses a fresh destination,
disables old credentials and revokes unused approvals. There is no automatic
pruning, backup encryption or external backup service.

## Readiness and approval

`models.py` owns strict versioned snapshot and assessment shapes. `lint.py` runs
L1-L8 syntax, lexical, tag, risk-reference, provenance-format, question-marker and
selected-catalog checks. Behavioral syntax uses the official parser/compiler;
checklists require an explicit verification method. These checks do not prove
semantic correctness or the authenticity of evidence. Independent D1-D10 review
remains essential. Suspicious-instruction heuristics can quarantine known patterns
but are not a universal prompt-injection detector.

Exact plans bind the snapshot, review, source revision and current policy sources.
The policy fingerprint includes core runtime/check modules, rubric and operating
contracts; a changed fingerprint requires re-review. Approvals expire within
900 seconds and are bound to their issuing credential. Only a local seal action
is allowlisted. Sealing consumes approval and stores the full export in one
transaction. Concurrent/repeated requests retrieve the same export. Saving that
export to a file is separate, retryable and refuses overwrite.

## Imports, hosts and interface

The Markdown importer uses explicit user-selected files and records source hashes.
The Linear reader accepts an explicitly supplied read-only API key and team scope,
uses fixed read-only GraphQL queries, checks optional project scope, paginates
comments, caps requests/bytes and refuses redirects or partial/error responses.
Live Linear validation is still required. It does not fetch arbitrary linked
pages, attachments or every possible issue field; it cannot guarantee an atomic
snapshot of concurrently edited comments.

The workbench is escaped, static HTML. It displays source diffs, questions,
evidence, reviews, exact plan and events. No JavaScript, remote assets, forms or
write actions are embedded. Approval stays in the authenticated CLI.

Ten agent profiles retain the reasoning process. The controller does not invoke
models, authenticate that two model deployments are genuinely independent, or
prove that each reasoning sub-stage occurred. Native host smoke tests and a
human-labelled model-quality benchmark remain separate work.

## Primary implementation references

- SQLite transaction semantics: https://www.sqlite.org/lang_transaction.html
- Official Gherkin Python parser/compiler: https://github.com/cucumber/gherkin
- Pinned parser distribution: https://pypi.org/project/gherkin-official/
- Linear authentication and errors: https://linear.app/developers/graphql
- Linear pagination: https://linear.app/developers/pagination
- Linear rate limits: https://linear.app/developers/rate-limiting
