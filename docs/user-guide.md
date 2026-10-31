# Clarity user guide

Follow [Quickstart](agent/QUICKSTART.md) first. The shipped configuration is
fictional; actual project configuration and all runtime evidence stay private.
[AGENTS.md](../AGENTS.md) is the canonical operating policy.

## Entry points

| Request | Entry point and behavior |
|---|---|
| Review DEMO-1234 | `story-orchestrator`, review mode by default |
| Review DEMO-1234 in apply mode | Same pipeline; approved READY output updates the description and AC field |
| New requirement: export my reading list | `story-intake`, one question at a time, duplicate check before drafting |
| Break down this specification | `story-creator`, proposes evaluated slices without creating issues |
| PO answered on DEMO-1234 | `story-po-responder`, incorporates sourced answers and re-runs the gate |
| Clean up closed runs | `skill-run-cleanup`, explicit local pruning after live verification of published evidence |

`DEMO-1234` is a fictional example key. Use your own configured project for real work.
Mode is fixed at run start. Stage agents redirect to the orchestrator unless
called by it or by intake as explicitly permitted in their profiles.

## Pipeline

Read the relevant issue fields and context → investigate → evaluate → rewrite
when needed (max three iterations) → quality gate → PO analyst and challenger
when questions remain → re-gate changes → stage for explicit approval → approved
write and read-back verification.

Investigation is LIGHT or DEEP according to risk and context. Intake always uses
DEEP, confirms affected and excluded scope, and checks for existing work before
creating anything. A duplicate redirects to existing-story review. Precedent is
marked `[INFERRED from KEY]`; another story is never proof of a new requirement.

The rubric has ten dimensions (D1–D10) and ten mechanical checks (L1–L10).
Unavailable checks are NOT_RUN; instructions alone are not evidence that a parser
ran. A local/pasted story can be prepared without an integration, but remote
reads, writes, and log-book publication remain blocked until configured.

## Read the short requirement

`{story_id}-rewrite.md` separates `## Jira payload` from
`## Review notes (run docs only — not posted)`. Only the payload goes to Jira.
It includes every fact needed to build and verify, the evidence link, confirmed
scope and dependencies, and format-appropriate ACs. Sources, rationale, risk
mapping and review history stay in evidence. A glossary or source table does not
belong in the payload; explain essential terms inline.

Behavioral work uses declarative Gherkin. Non-behavioral work uses measurable
outcome checklists. Target 3–6 ACs, max 8 (a Scenario Outline counts once). Target
8,000 description characters after Jira conversion; WARN above 10,000 and FAIL
above 20,000. Checklist items over 250 characters warn. Tighten before adding;
split when essential build details cannot fit. See the
[fictional examples](../examples/lean-requirement.md).

## Context-aware engineering standards

Clarity can consult the [public standards pack](../Reference/standards/README.md)
during investigation and evaluation. It uses
[NASA's requirements validation checklist](../Reference/standards/nasa-requirements.md)
as a research-based baseline and chooses only relevant API/security, UX,
accessibility or operational questions for the actual story. It records the
edition, source and applicability in private review evidence.

This is not a universal compliance checklist, a substitute for code tests or a
new readiness gate. The ten existing DoR dimensions and the AC budget still
apply. `NOT_APPLICABLE`, `UNKNOWN` and `NOT_RUN` must be distinguished;
unverified external recommendations are questions, not invented product
requirements.

## Approval and resulting state

Every Jira write needs explicit approval of the staged result. READY alone,
autonomy, silence, or a timeout is not approval. Re-read the destination and verify
the target before writing. Business/non-software tasks identified by a verified
project mapping retain the source workflow's comment-only restriction.

| Command | Review mode | Apply mode |
|---|---|---|
| approve | Post questions-only `ai-reviewed` comment | Update description and AC field only if READY; no comment |
| approve + apply | READY only: post comment and update description/AC | Not a mode switch; use ordinary approval |
| just add comments | Comment and evidence only; never description/AC | Same explicit comments-only override |
| approve with open questions | PO override: write description/AC plus comment, retain questions visibly | Same PO override; retain questions visibly |
| amend | Incorporate changes, re-gate, stage again | Same |
| deny | Close as rejected, no Jira write | Same |

A written questions comment or PO override with unresolved questions remains
`awaiting_po`. Comments-only on READY stays staged for an approved description
write. A run closes as `done` only when READY, zero open questions, and its
approved Jira outcome has been written. See the canonical approval matrix for
all exceptions and state transitions.

Intake offers approve, approve with open questions, amend, or deny; it cannot
apply or add comments to an issue that does not exist. Approval creates the issue,
migrates the temporary run ID to its real key, publishes evidence and updates the
decision index. PO-override creation remains awaiting PO when questions remain.

## Evidence and privacy

The ignored `docs/agent/run-status.md` points to active, awaiting-PO and closed
runs. Each run has its own ignored `docs/agent/runs/{story_id}/` folder. Read the
run summary first, then the scorecard, rewrite, quality gate, sources, and decisions.
First-run register templates live in `docs/agent/templates/registers/`.

The configured Confluence log-book subtree holds the full evidence, including
verbatim inline artifacts and verified attachments where supported. Grounding and
specification pages are read-only. An unset log-book destination grants no write
authority. Record integration failures without inventing a published page.

Cleanup is never automatic. It removes only explicitly selected closed run folders
with a live-verified evidence page, keeps status pointers, and appends a pruning
ledger. Active, awaiting-approval and awaiting-PO runs are never eligible. Actual
configuration, working registers, reference files and run artifacts must never be
committed. See [security](../SECURITY.md).
