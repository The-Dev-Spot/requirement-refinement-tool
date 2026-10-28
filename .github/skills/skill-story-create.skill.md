# Skill: skill-story-create

## Purpose
Decompose a Confluence specification or epic into candidate user stories ready for
external handover — each an independently valuable, testable slice that has been
scored by `skill-story-eval`. Invoked by the standalone `story-creator`.

## Reads
- The spec/epic (via `skill-confluence-rag`, with provenance preserved)
- `rubric/definition-of-ready.md`, `docs/risk-register.md`, `steps/catalog.md`
- `docs/agent/learnings.md`

## Writes
- `docs/agent/runs/{spec_id}/breakdown.md` (proposed stories + coverage + sequencing)
- `docs/agent/runs/{spec_id}/decision-log.md` (append: slicing rationale, clarifications)

## Steps
1. **Read the spec** and identify the distinct capabilities/outcomes it implies.
   For each, capture the exact source section + last-modified date.
2. **Clarify — capped at 3 questions.** If ambiguous, raise at most three highest-
   impact clarifying questions to the internal PO/SME (never the receiving dev
   team). Answered -> fold in (with provenance). Unanswered ->
   `# OPEN QUESTION -> PO:` on the affected story. **Never invent an answer to
   avoid asking.**
3. **Slice into vertical stories** — thin end-to-end behaviors ("classify a B2C
   application"), not layers ("build the DB"). Add explicit non-behavioral enabler
   stories where needed (checklist, not Gherkin).
4. **Draft each story** to the rubric, within its "Proportionality" budget
   (lean payload, max 8 ACs, target 3–6; see `examples/lean-requirement.md`): shape &
   value (`D2`), declarative Gherkin or checklist per type (`D3`), concrete ACs
   (`D4`), a negative check where a register risk applies (`D5`, mapping in the
   review notes), provenance in the review notes (`D6`). Reuse catalog step
   phrasings. A capability needing more than 8 ACs is split into more stories.
5. **Score every story with `skill-story-eval`.** Any story that does not reach the
   gate is fixed or dropped — never propose a story that fails its own rubric.
6. **Map dependencies and sequence** the stories (`D8`) so the receiving team can
   build them in a sane order.

## Output quality rules
- Every proposed story records its own `skill-story-eval` gate result.
- Provenance from the spec survives into each story (page/section + last-modified).
- At most 3 clarifying questions; everything else is an open question.

## Guardrails
- **Propose, never apply.** Output is a proposed breakdown for a human to create
  in the target Jira project (`.github/project-config.yaml`); do not create/edit
  issues directly.
- No invented requirements; the spec is the source, gaps are open questions.
- Do not let retrieval paraphrase away numbers (ratios, rating bands, limits) or
  drop last-modified dates.
- No stage ownership; `story-creator` owns the flow.
