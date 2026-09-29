# Quality handoff implementation — 29 September 2026

## Fixed product goal

The product is the quality of the requirement received by developers and testers.
An expert specification, partial analysis and everyday request must meet the same
output standard. Gherkin is canonical, including reuse as Cucumber/Xray test
specifications. Clarity remains standalone, private and vendor-neutral.

## Delivered

- Minimal plain-language briefs, guided/concise presentation and a separately
  validated complete-draft contract. No weaker readiness threshold for novices.
- Source-linked statements with exact quotations, source hashes and separately
  recorded reference applicability. Citation existence is not claimed as entailment.
- Operator-selected versioned policy, not a risk register supplied by the draft.
- Stable questions with consequences and priority; authenticated answers, explicit
  merge/out-of-scope decisions, and superseded answers excluded from active support.
- Official Gherkin AST/compiler checks, stable scenario IDs, rule/constraint links,
  and explicit positive/negative/boundary/alternative coverage or reviewed reasons.
- Independent, snapshot-bound review of every statement and scenario, ten semantic
  criteria and materially different interpretations. Writer self-scores are absent.
- Exact finding/revision/context resolutions: reviewers handle wording warnings;
  operators adjudicate suspicious instruction patterns; hard failures stay blocked.
- A bounded, opt-in local-model drafting/interview stage and fresh review stage,
  with persisted attempts, budgets, structured output and no tools/approval authority.
- Interactive loopback workbench: ordinary-language capture, source review,
  questions, diffs, coverage, role-specific actions and exact handoff approval.
- Immutable approval-bound local ZIP exports. acceptance.feature preserves the
  approved UTF-8 text, including line endings; profiles select intended import
  guidance, not a live Xray integration or a second generation of the criteria.
- A same-need/three-starting-points evaluation harness that counts missing outputs
  and separates groups. Fixtures are synthetic and not human-ratified labels.
- Versioned backup/restore includes both legacy and new refinement tables, rejects
  incomplete namespaces, verifies chains/hashes and disables old credentials.

## Validation and qualification

Regression coverage includes contracts, provenance, authority, coverage, false
positives, missing parsers, model output validation, role separation, stale inputs,
atomic batches and exports, concurrency, HTTP origin/CSRF/session handling,
source escaping, local transport, restart and backup recovery. CI installs the
hash-pinned official parser and runs the full old and new suites on Python 3.11
and 3.13. Exact results and tested SHA belong in the PR/CI record, not a stale
hard-coded progress count in this document.

The implementation environment could not download the official parser. Local
parser-dependent tests are explicitly skipped; that is not evidence of parser
success. CI must run them before acceptance. No live model or Xray account was
used. The loopback HTTP server was exercised through real local HTTP tests;
model transport is mocked in contract tests.

## Deliberate boundaries

This is not a guarantee of semantic correctness or equal outcomes in practice.
Quoted passages can exist but fail to support a statement; independent review and
human approval must assess meaning and decision authority. The parity corpus has
one synthetic business need in three presentations; it is an executable starting
point, not a statistically meaningful or human-validated benchmark.

The runner has two explicit stages, incorporating the established reasoning
responsibilities. It does not autonomously dispatch all ten specialist profiles.
It reads only selected context and does not browse systems, invent decisions,
write trackers or call a development pipeline. Live model quality, model-provider
privacy, actual Xray edition behavior and native editor integrations need pilots.

The web workbench binds only to 127.0.0.1 and uses local capability/session controls.
It is not a public server, enterprise sign-in, tenant isolation or a sandbox against
its OS owner. Authors are isolated by run ownership; reviewer/operator capabilities
span the trusted workspace. Backups are not encrypted; no automatic deletion runs.
Legacy checklist exports remain separately labelled legacy artifacts and do not
satisfy or bypass the new Gherkin-first handoff contract.
