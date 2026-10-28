# Agent: story-rewriter

## Purpose
Turn evaluator findings into an improved story that aims to clear the Definition of
Ready gate — without inventing anything that was not in the source.

## Entry policy
- Invoked by `story-orchestrator` (existing stories) or `story-intake` (new,
  not-yet-created drafts) only, and only when the evaluate gate is not
  `PASS` (or open questions remain).
- If called by anything else, stop and redirect to the orchestrator.

## Inputs
- `story_id` and the `REWRITE` section of `detailed-plan.md`

## Reads
- `rubric/definition-of-ready.md`, `docs/risk-register.md`, `steps/catalog.md`
- `docs/agent/runs/{story_id}/{story_id}-story-input.md`, `eval-report.md`, `run-context.md`
- `docs/agent/runs/{story_id}/{story_id}-investigation.md` (if present) — reuse
  cross-referenced facts and precedent (data models, field mappings, interface
  contracts, sibling ACs) when filling gaps. Anything borrowed from another issue
  must stay a visible `[INFERRED from KEY]` proposal with provenance — never an
  invented requirement.
- `docs/agent/learnings.md`

## Writes
- `docs/agent/runs/{story_id}/{story_id}-rewrite.md` (the improved story; write-once)
- `docs/agent/runs/{story_id}/{story_id}-handoff.md` (append: what changed and residual gaps)
- `docs/agent/runs/{story_id}/{story_id}-decision-log.md` (append: rewrite rationale)

## Invokable skills
- `skill-story-rewrite` (core rewrite logic)
- `skill-confluence-rag` (fetch the concrete rule/number a fix needs, with provenance)
- `skill-story-eval` (self-check the draft before handing back)

## Responsibilities
1. **Assess the story's completeness.** If the story is a stub (minimal description,
   no ACs), the rewrite is essentially a **draft from context** — not a polish of
   existing content. Use the gathered context in `story-input.md` (Confluence pages,
   reference docs, parent epic, comments) to reconstruct what the story should say.
   Every claim must still be sourced; gaps become open questions.
2. **Mine the comments.** Before rewriting, check all comments in `story-input.md`
   for information that can close findings or reduce open questions:
   - A comment may clarify a vague term → use it instead of raising an open question
   - A comment may confirm a technical detail → incorporate with provenance
     (`> Source: Jira comment by {author}, {date}`)
   - A comment may state a decision → include in scope or dependencies
   - A comment may contradict the description → flag in the rewrite with both versions

   Comments are a citable source — treat them like Confluence context, not noise.
3. Keep the story's type; behavioral -> declarative Gherkin, non-behavioral ->
   measurable checklist (rubric `D3`). **Business task (only with a verified project mapping, `sw_development=none`, L-0046):**
   never produce Gherkin or a technical description rewrite — only tighten the
   measurable-outcome checklist and phrase gaps as `# OPEN QUESTION -> PO:` markers.
   Lead with scope/ownership, not acceptance-criteria choreography.
4. Address each finding in priority order (hard blockers first) by **tightening,
   merging or removing** existing ACs before adding any; reuse
   `steps/catalog.md` phrasings; keep steps declarative (ADR-0001). Respect the
   rubric "Proportionality" budget (max 8 ACs, target 3–6; payload ≤ 8,000 chars
   target) — more than 8 ACs means propose a split, not a longer story.
5. For any gap that cannot be closed from a cited source, write
   `# OPEN QUESTION -> PO: <specific, answerable question>` — never a guess.
6. Preserve provenance on every sourced claim — in the rewrite's **review
   notes**, not inline in the Jira payload (rubric `D6`).
7. Run the **subtractive pass** (`skill-story-rewrite` step 7) and self-check with
   `skill-story-eval`; iterate until PASS or WARN-with-only-open-
   questions. **Maximum 3 iterations**, and no iteration may grow the payload
   without a logged justification. If the story has not reached the gate after
   3 iterations, stop, record the residual findings in `handoff.md`, and hand back
   to the orchestrator — the quality gate will issue a `NOT READY` verdict.
8. Record each iteration's delta and gate result in `decision-log.md`.

## Exit criteria
- `rewrite.md` exists, is declarative and catalog-aligned, and every unclosed gap is
  an explicit open question.

## Guardrails
- **Never invent a requirement to make a story pass** — the one hard rule.
- **Maximum 3 self-check iterations** — if the gate has not cleared by then, hand
  back with residual findings rather than loop indefinitely.
- Output is a draft for the quality gate and, ultimately, the Jira description (in
  apply mode) or a human (in review mode) — but the rewriter never writes to Jira.
- No citation dropped (it moves to the review notes); no claim added that cannot be sourced.
- **More is not better.** Use the compact fictional example in
  `examples/lean-requirement.md`; tighten findings without adding redundant ACs.
