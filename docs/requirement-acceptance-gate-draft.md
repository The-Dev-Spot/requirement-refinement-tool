# Requirement Acceptance Gate — implementation draft

**Status: READ-ONLY PROPOSAL VALIDATOR IMPLEMENTED; trusted ACCEPTED issuer
NOT implemented or ratified.** Architecture draft, 2026-11-01.

## Implemented validation slice (non-authorizing)

The local `scripts/accept_requirements.py` CLI validates a frozen story,
operator-supplied current story snapshot, frozen independent review, the exact
review-policy JSON bytes, a separate acceptance-policy JSON, and the existing
Forge v2 ZIP. It produces a strict `clarity-requirement-acceptance-proposal`
with **CANDIDATE**, **NEEDS_DECISION**, or **BLOCKED** — NEVER `ACCEPTED`.

```sh
python3 scripts/accept_requirements.py \
  --story /private/HOM-123.story.json \
  --current-story /private/HOM-123.current.json \
  --canonical-source /private/HOM-123.original-issue-description.md \
  --current-canonical /private/HOM-123.current-issue-description.md \
  --review /private/HOM-123.review.json \
  --review-policy /private/review-policy.json \
  --acceptance-policy /private/acceptance-policy.json \
  --handoff /private/HOM-123-v2.zip \
  --source-system linear --source-ref HOM-123 --revision 1 \
  --tracker-revision 2026-11-01T07:15:35.085Z \
  --output /private/HOM-123.acceptance-proposal.json
```

**Provenance semantics:** `source.content_sha256` binds the **reviewed
story JSON**. `source.canonical_content_sha256` separately binds the
**original UTF-8 tracker issue description**. `source.tracker_revision`
carries its tracker revision/updatedAt, distinct from the Forge v2 handoff's
integer `revision`. Both source snapshots must match locally. This is still
*caller-supplied evidence*; only the later authenticated tracker adapter can
prove current revision and issue ownership. Existing v2 ZIP format is unchanged.

The acceptance validator now re-derives the authoritatively versioned
D1–D10 rubric SHA from `rubric/definition-of-ready.md`; it rejects
review reports missing that hash, model-reported identity, distinct stage
sessions or a matching exact prompt digest. These receipt fields are
structural crosschecks, **not** signatures or source truth. The same
validation applies to Claude Code and operator-configured external model
adapters. See [model adapter protocol](independent-quality-review-pilot.md).

**Important limitations**: both story files are still supplied by the caller;
this CLI cannot query Linear to authenticate "current", cannot verify real model
execution or an approved policy issuer, and does not cryptographically authenticate
the resulting JSON. A fabricated model receipt might pass syntactic scrutiny,
but a `CANDIDATE` is still only untrusted **data for a separate supervisor**.
The supervisor **must** re-fetch current source and independently authenticate
review run/session and policy adoption before it can issue `ACCEPTED`.
No client may treat a proposal as a Forge WorkOrder or implementation permission.

For this initial conservative pilot, `requirement.md` in the ZIP must be the
*exact UTF-8 text of the story's reviewed `payload`*, and each non-behavioral
ZIP criterion text must exactly match the corresponding reviewed story criteria
in order. Behavioral Gherkin must exactly match the reviewed `feature`. This
deliberately rejects independently rewritten/exported text until we design and
validate a **bound reviewed-artifact transformation contract**. The source
revision supplied to the CLI must match the v2 handoff revision integer.

The example policy remains `DRAFT` with automatic acceptance disabled; this
yields `NEEDS_DECISION` even for syntactically clean evidence. An operator-
provided `status: APPROVED` with `do_r_and_risk_policy_ratified: true` may
yield `CANDIDATE` but **does not prove actual adoption**. The trusted decision
service is intentionally deferred until we review this contract together.


**Owner:** Clarity toolkit (quality evidence and data-only proposal); the trusted project
acceptance supervisor / Forge City (authenticated acceptance decisions and admission).
**Related:** `rubric/definition-of-ready.md`,
`scripts/quality_review.py`, `docs/forge-handoff.md`, HOM-1982,
HOM-1981 and HOM-1977.

## Objective

Give Forge an *accepted, version-locked requirement* that is correct, testable and
within the product owner's delegated policy. Preserve human review for material
ambiguity, security/privacy impact and architecture changes. Routine low-risk
accepted defects should not require a human Start **per issue**.

**Do not confuse three distinct gates:**

1. **Intake eligibility:** n8n/tracker accepts an event as worth investigating
   (does not authorize implementation).
2. **Requirement acceptance:** Clarity's quality checks passed and a **trusted
   human or previously approved, scoped policy** accepted the *exact requirement*.
3. **Execution admission:** Forge City's separate WorkOrder supervisor authorizes
   tools, repo, branch, worker lane and draft-PR actions. Neither a requirement
   ZIP nor an acceptance record grants production writes, merge/deploy, privilege
   escalation, or CRITICAL routing.

## Existing assets — preserve

- Deterministic L1–L10 checks and a *real* three-session investigator, evaluator,
  blind challenger runner (currently local and model execution not yet qualified
  against real M0 examples). The reviewer outputs `REVIEWABLE_CANDIDATE`, **not**
  `READY` or trusted approval.
- Clarity typed exporter v2 packages `requirement.md`, `criteria.json`,
  `handoff.json`, and optionally `acceptance.feature`, with ordered
  `AC-` IDs and digests. ZIP is immutable data, never proof of approval.
- Forge imports v2 and maps stable `AC-` IDs to implementation `SC-` IDs; import
  validates data but must not authenticate a user or authorize execution.
- No extra mandatory Confluence/Jira/logbook, no new service or paid inference
  dependency introduced by this contract.

## Minimal acceptance boundary

A small deterministic Python `accept_requirements.py` and strict JSON Schema
can prepare a **proposal** from a frozen review + ZIP. This public repo should
only produce `CANDIDATE | NEEDS_DECISION | BLOCKED` proposals; a proposal cannot
self-certify the owner's signature, authenticate a Linear revision or declare
`ACCEPTED`.

The **trusted project adapter/supervisor** later:
- reads canonical tracker source/version and authorized project policy directly,
  with source ownership out of reach of agent input;
- verifies run receipts (real distinct invocations, model identity, input hashes,
  policy hash, checker version) from its own trusted execution record — not a
  string in model output or in a user-supplied JSON document;
- compares the original issue snapshot and source decision index to the current
  authoritative tracker revision; source `updatedAt` is not sufficient alone:
  bind a SHA-256 of exact canonical content and reject stale reads;
- validates L1–L10 statuses (`PASS` or explicitly accepted N/A only; any
  required `NOT_RUN`, `WARN` or `FAIL` denies), D1–D10 `PASS`, no open
  questions or unresolved independent challenger findings, and required
  project-specific risk controls;
- verifies full *exported ZIP byte SHA-256*, ordered AC IDs, source and policy
  hashes. The accepted subject is **that exact package**, not any package
  bearing the same story ID;
- evaluates a **versioned project policy**. For an owner-preapproved LOW-risk
  routine defect, issue `policy_auto` acceptance. Otherwise request an
  authenticated product/security-owner decision. Record who/what, why, when,
  expiry, revision, idempotency key and (where needed) issuer signature;
- maintains append-only audit/revocation state in trusted storage; current
  acceptance is checked **again at dispatch**, not just at ZIP creation.

**Policy trust:** `adopted: true` in `quality_review.py` is user-supplied
metadata, not verified organizational adoption. No automatic acceptance until
the trusted adapter can verify adoption and identity independently. Example
config stays deliberately `DRAFT` and `auto_accept.enabled=false`.

## Acceptance proposal v1 (untrusted data)

Draft schema: `schemas/requirement-acceptance-proposal-v1.schema.json`.
A proposal contains only:
- `source.system/ref/revision/content_sha256` — exact reviewed source revision;
- `handoff_sha256` — hash of entire deterministic Forge v2 ZIP;
- `criterion_ids` — ordered, stable identifiers, verified against ZIP;
- `quality_report_sha256` — hash of complete bound quality review report;
- `project_policy.id/revision/sha256` — expected policy identity;
- `result = CANDIDATE | NEEDS_DECISION | BLOCKED` and `reasons`.

The schema **does not support** `approved`, `can_execute`, arbitrary
`tool_permissions`, `environment`, `CRITICAL`, or `ACCEPTED`. Such fields
are rejected. Even a schema-valid CANDIDATE must be independently evaluated
and authorized by the trusted project supervisor.

A separate accepted-record API/ledger entry may later store verified
`ACCEPTED` with authenticated issuer identity, constraints, expiry and a
cryptographically verifiable signature/attestation if exchanged across trust
boundaries. Do not put it inside `handoff.json` and do not change v2 schema.

## Recommended lifecycle

`DRAFT -> QUALITY_REVIEWED -> ACCEPTANCE_CANDIDATE -> ACCEPTED`
with transitions to `NEEDS_INFORMATION`, `NEEDS_DECISION`, `BLOCKED`,
`REJECTED`, `SUPERSEDED`, `EXPIRED`, `REVOKED`.

- A materially incomplete requirement can still be safely **investigated**
  under a distinct, tightly constrained investigation-only WorkOrder.
- Once any source text, decision version, acceptance criterion, risk policy or
  ZIP changes, previous acceptance is **superseded/revoked** and cannot authorize
  the new content.
- D1–D10 semantic completeness remains risk-scoped; irrelevant UX controls
  aren't imposed on backend-only work. Missing actual applicability evidence
  is not automatically NOT_APPLICABLE.
- Source content / diff / model output cannot grant acceptance or override
  project policy. Store reviewed and accepted versions outside agent-writeable
  surfaces with atomic compare-and-swap updates and replay protection.

## Illustrative *proposed* policy matrix (not ratified)

| Class | Requirement acceptance | Forge City behavior |
|---|---|---|
| Routine low-risk defect, complete approved expected behavior, clean reviewers | `policy_auto` after trusted preauthorization | Scoped code/test/draft PR; no merge/deploy |
| Insufficient evidence or unverified reproduction | `NEEDS_INFORMATION` | Optionally safe investigation-only work |
| Contradictory approved requirements (e.g. HOM-1972) | `NEEDS_DECISION` | Block implementation; preserve original source |
| Security/privacy/authn or major architecture/migration impact | Authenticated human/security owner according to adopted policy | May plan, no unauthorized implementation |
| Production-live incident | Urgent investigation if registry confirms risk lane | Critical worker queue is **not** acceptance override |
| Stale source, changed ZIP, invalid issuer, draft policy, unrun reviewer | `BLOCKED` | No implementation handoff |

## Implementation slices and strict acceptance tests

### Slice A — pure Clarity acceptance proposal
- Strict schema + example DRAFT policy + deterministic validator, **read-only**;
  no model inference, no network and no authority.
- Full v2 ZIP hash, source snapshot hash and reviewer report SHA required.
- Tests: well-formed candidate, unexpected `approved` rejected, missing
  review evidence blocked, WARN/NOT_RUN blocked, unbound AC IDs blocked,
  modified ZIP and stale source blocked.
- Existing Clarity exporter and Forge v1/v2 importer remain unchanged.

### Slice B — trusted acceptance decisions and storage
- Signer/principal and policy revision verified out-of-band by trusted host,
  no user/story-controlled toggle. Versioned allow rules and negative tests.
- Durable idempotent decision ledger; uniqueness by source ID + revision +
  package hash + policy digest; atomic compare-and-swap on source revision.
- Separate decisions: `human` and `policy_auto`; expiry, revocation, audit.

### Slice C — Forge City verifier
- Verify accepted ledger record or signed sidecar and exact ZIP digest before
  dispatch; check acceptance still valid, source current, review receipts bound.
- WorkOrder owns independent repo/branch/tool/worker-lane permissions; policy
  denies merge, deployment, prod mutation and unauthorized CI changes.
- Enforce same identity, artifact and revision throughout retries.

### Slice D — qualification
- Unit/property/negative tests on tamper, stale source, fake model/human
  signer, replay, duplicate jobs, unratified risk policy and checker WARN.
- M0 golden case **HOM-1972** MUST fail acceptance for the conflicting worker
  capacity and old per-job Start instructions. HOM-1945 checks risk/security;
  HOM-1943 verifies nonbehavioral evidence and prerequisites.
- Once actual independent models are authenticated locally, run original
  issues at frozen revisions; record measured missed findings, false positives,
  tokens, costs, and eventual Forge test trace. CI alone is **not** a live run.

## Definition of done

An automatic approval is never issued based solely on a model verdict or an
unverified policy flag. A high-quality, preauthorized low-risk requirement
receives a trusted, traceable acceptance record for the exact v2 ZIP without
requiring per-ticket manual approval; any unknown/changed/unsafe input fails
closed. Forge's existing importer stays data-only, and only the separately
trusted supervisor can begin implementation. No background workers or extra
logbooks are prerequisites for the small initial validator.

**Research foundations:** NASA Appendix C; ISO/IEC/IEEE 29148; OWASP AI Agent
Security; OPA policy/testing; DSSE/in-toto attestations. Their controls should
be applied contextually, not assumed to impose binding product policy.
