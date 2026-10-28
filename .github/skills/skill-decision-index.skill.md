# Skill: skill-decision-index

## Purpose
Keep a compact, scannable index of material decisions taken across runs, so the
next person (or agent) can see what was decided and why without reading every
decision log. Mirrors the `spesa-agents` decision-index pattern.

## Reads
- `docs/agent/decision-index.md` (current index)
- `docs/agent/runs/{story_id}/{story_id}-decision-log.md` (source detail for the run)

## Writes
- `docs/agent/decision-index.md` (append one compact row per material decision)

## Steps
1. Identify decisions in the run's `decision-log.md` that are **material** —
   they change scope, a gate outcome, a rubric interpretation, or a handover-
   blocking open question. Skip trivia.
2. Append one row per decision: `date | story_id | decision | rationale | link`.
   Convert any relative date to an absolute date.
3. Keep it compact — one line each; the detail stays in the run's decision-log.

## Output quality rules
- One line per decision; no duplication of full rationale (that lives in the log).
- Every row links back to the run's `decision-log.md`.

## Guardrails
- Append-only; never rewrite or delete prior index rows.
- No stage ownership; invoked by agents (typically `story-quality-gate`).
