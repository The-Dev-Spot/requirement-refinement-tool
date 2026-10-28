# Skill Template

Copy this for a new story-quality skill. Keep it self-contained and reference the
rubric by section id (e.g. `D3`, `L5`) rather than restating it.

## Purpose
One-line capability summary.

## Reads
- convention/context files required (e.g. `rubric/definition-of-ready.md`, `docs/risk-register.md`)
- run docs required (e.g. `docs/agent/runs/{story_id}/{story_id}-run-context.md`)

## Writes
- run docs this skill may update (and their write semantics per `../agents/runtime-doc-contract.yaml`)
- optional `decision-log.md` entries

## Steps
1. Numbered, deterministic where possible.

## Output quality rules
- Concrete, binary, evidence-bearing outputs. No vague terms.

## Guardrails
- No stage ownership (an agent owns transitions).
- No out-of-scope writes.
- No invented requirements; gaps become `# OPEN QUESTION -> PO:` markers.
- Cite provenance for doc-grounded claims.
