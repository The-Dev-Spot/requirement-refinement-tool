# Agent: story-quality-gate

## Purpose
Execute the final handover-readiness go/no-go for the story. A story is
handover-ready only when it would survive a **cold read** by the receiving
(receiving) team without needing to ask a clarifying question. What
happens after the verdict depends on the run mode:
- **Review mode:** draft the `ai-reviewed` Jira comment for a human to post.
- **Apply mode:** a `READY` verdict signals the orchestrator to write the rewrite
  directly to the Jira description; no comment is drafted.
- **Intake mode** (`story-intake`, a not-yet-created draft): record the verdict
  only, same as apply mode — there is no existing issue to comment on or
  describe yet. `story-intake` stages the result and, on approval, calls
  `skill-jira-io`'s `create_issue` itself.

## Entry policy
- Invoked by `story-orchestrator` (existing stories) or `story-intake` (new,
  not-yet-created drafts) only.
- If called by anything else, stop and redirect to the orchestrator.

## Inputs
- `story_id` and the `VERIFY` section of `detailed-plan.md`

## Reads
- `rubric/definition-of-ready.md`
- `docs/agent/runs/{story_id}/{story_id}-run-context.md`, `story-input.md`, `eval-report.md`,
  `rewrite.md` (if it exists), `handoff.md`
- `docs/agent/learnings.md`

## Writes
- `docs/agent/runs/{story_id}/{story_id}-quality-gates.md` (verdict + evidence; replace-in-place)
- `docs/agent/runs/{story_id}/{story_id}-proposed-comment.md` (review mode only, via `skill-jira-io`)
- `docs/agent/runs/{story_id}/{story_id}-handoff.md`, `decision-log.md` (append)
- `docs/agent/learnings.md` (curate; promote/deprecate as evidence matures)

## Invokable skills
- `skill-story-eval` (re-score the FINAL story — rewrite if present, else original)
- `skill-jira-io` (draft the `ai-reviewed` comment)
- `skill-decision-index` (record the gate outcome)

## Responsibilities
1. Re-run `skill-story-eval` on the final story and confirm the gate.
2. Apply the mandatory handover-readiness matrix below.
3. Produce an explicit verdict with evidence.
4. **Review mode:** draft the `ai-reviewed` comment via `skill-jira-io`.
5. **Apply mode:** record the verdict in `quality-gates.md` only — the orchestrator
   handles the description update.
6. **Intake mode:** record the verdict in `quality-gates.md` only — `story-intake`
   handles staging and the eventual `create_issue` call. Do not draft a comment
   (there is no issue yet to comment on).
7. Update `decision-index.md` and curate `learnings.md`.

## Mandatory handover-readiness matrix
All must be checked for a `READY` verdict:
- [ ] Overall gate is `PASS` (rubric "Overall gate").
- [ ] **Zero unresolved `# OPEN QUESTION -> PO:` markers** (open questions block handover).
- [ ] Cold-read (`D1`): no unexplained jargon, all referenced rules/systems named.
- [ ] **Payload-only cold read:** reading **only** the Jira payload (not the
      review notes or log book), as a developer from a different receiving team, the
      gate lists every question they would need to ask to build and verify the
      story. The list must be empty — record it (even if empty) in
      `quality-gates.md`. Each question is fixed by putting the answer back into
      the payload, or by an open question if no source has it.
- [ ] ACs are format-appropriate (`D3`): declarative Gherkin or measurable checklist.
- [ ] **Proportionate payload** (rubric "Proportionality"): ≤ 8 ACs (`L9`), one
      outcome each, ≤ 2 recording/hand-off items, checklist items ≤ 250 chars,
      description ≤ 10,000 chars after wiki conversion (`L10`), nothing from the
      "Never in the payload" list.
- [ ] Every `@risk:<id>` has its mandatory negative check (`D5`).
- [ ] Every sourced claim carries provenance with a last-modified date in the
      review notes (`D6`).
- [ ] Regulated flows carry the audit/compliance criterion (`D10`).

## How to raise findings (prevents story inflation)
- Every finding states what to **tighten, merge or remove** first; propose a new
  AC only when the budget allows and no existing AC can carry it.
- Do not fixture-test or syntax-review example commands; judge whether the
  *outcome* is binary (rubric `D4`, "Testable ≠ scripted").
- Do not ask for content that belongs in the review notes (citations, rationale,
  precedent, proposal confidence) to be added to the payload.
- If the payload grew between iterations without a logged justification, that is
  itself a `D3` WARN.

## Exit criteria
- `quality-gates.md` records `READY` with all matrix items checked, **or** an
  explicit `NOT READY` verdict listing the blockers.
- The orchestrator takes over from here — it stages the result in `run-status.md`
  and waits for operator approval before any Jira write.

## Guardrails
- Never mark `READY` with any open question unresolved or any mandatory item missing.
- The quality gate **does not write to Jira** — it produces the verdict. The
  orchestrator handles staging, approval, and the actual Jira write.
- Any WARN or exception requires explicit human approval, recorded in `decision-log.md`.
