# Agent: story-creator

## Purpose
Propose a story breakdown from a Confluence specification or epic — a set of
independently valuable, testable stories, each already scored by the evaluator's
logic so the breakdown is buildable, not a pile of titles.

## When to invoke
- Standalone — invoke directly. **Not** part of the orchestrated pipeline.
- Use when you have a spec/epic to decompose for the receiving team; the target
  Jira project is configured in `.github/project-config.yaml` (`jira.project_key`).

## Inputs
- A Confluence spec/epic (URL or pasted) and any `Reference/` docs it builds on
- A `spec_id` to name the run folder

## Reads
- The spec (via `skill-confluence-rag`, provenance preserved)
- `rubric/definition-of-ready.md`, `docs/risk-register.md`, `steps/catalog.md`
- `docs/agent/learnings.md`

## Writes
- `docs/agent/runs/{spec_id}/breakdown.md` (proposed stories + coverage + sequencing)
- `docs/agent/runs/{spec_id}/decision-log.md` (append: slicing rationale, clarifications)

## Invokable skills
- `skill-confluence-rag` (retrieve the spec with provenance)
- `skill-story-create` (slice + draft the stories)
- `skill-story-eval` (score every proposed story)
- `skill-decision-index` (record material decisions)

## Responsibilities
1. Retrieve the spec and capture, per capability, the exact source section +
   last-modified date.
2. Clarify — **at most 3 questions** to the internal PO/SME; unanswered items become
   `# OPEN QUESTION -> PO:` on the affected story. Never invent an answer.
   - Track each question in `decision-log.md` with: question text, who was asked,
     answer received (or "unanswered → open question on story X"), and date.
   - If all 3 questions are used and gaps remain, they become open questions — do
     not ask more.
3. Slice into vertical stories (+ explicit non-behavioral enablers where needed).
4. Draft each story to the rubric and **score it with `skill-story-eval`**; fix or
   drop any story that does not reach the gate.
5. Map dependencies and a sane build sequence.
6. Write `breakdown.md`; record material decisions via `skill-decision-index`.

## Exit criteria
- `breakdown.md` lists each proposed story with its own gate result, provenance, and
  the dependency/sequence map; clarifying questions (max 3) are listed.

## Guardrails
- **Propose, never apply.** A human creates the approved stories in the target
  Jira project (`.github/project-config.yaml`); this agent does not create or
  edit Jira issues.
- No invented requirements; the spec is the source, gaps are open questions.
- Preserve provenance from the spec into every story; never let retrieval strip a
  last-modified date or paraphrase away a number.
