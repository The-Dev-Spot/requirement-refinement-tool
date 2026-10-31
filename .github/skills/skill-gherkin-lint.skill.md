# Skill: skill-gherkin-lint

## Purpose
Deterministic pre-flight for a story. Runs the rubric's machine-checkable checks
(`L1..L10`) with no model involved, so a mechanically broken story can be failed
**before** any semantic scoring is spent. Invoked first by `story-evaluator`.

## Reads
- `rubric/definition-of-ready.md` (the `L1..L10` definitions, vague-term list, tag/marker syntax, AC budget)
- `docs/risk-register.md` (to resolve `@risk:<id>`)
- `steps/catalog.md` (for `L8` near-duplicate detection)
- The story under review (from `docs/agent/runs/{story_id}/{story_id}-story-input.md`)

## Writes
- The `Deterministic checks` section of `docs/agent/runs/{story_id}/{story_id}-eval-report.md`
- `docs/agent/runs/{story_id}/{story_id}-decision-log.md` (append: only if a judgement call was made)

## Execution availability
This is an instruction contract, not a bundled full lint implementation. Use a
verified parser/checker for actual runtime results. The optional maintainer
validator in `.github/validation/` checks repository fixtures and contracts only.
It does not score arbitrary stories or implement all L1–L10 checks. If a required
check is unavailable, record `NOT_RUN` and the missing capability; do not claim
it passed or establish READY from that result.

## Steps
1. **Classify** the story as behavioral or non-behavioral (rubric "Story types").
   Non-behavioral stories skip Gherkin-specific checks (`L1`, `L4`).
2. **L1 — Gherkin parses** (behavioral): `Feature`/`Scenario` present, steps in
   `Given -> When -> Then` order, no empty steps. *Hard.*
3. **L2 — Tag syntax**: each tag is `@<lower-kebab>`, `@risk:<id>` / `@nfr:<id>`, or the reserved optional `@case_<stable-id>` for Forge v2 handoff (e.g. `@case_AC-1`);
   no unknown namespace. *Hard.*
4. **L3 — Vague terms**: scan every AC against the rubric vague-term list; a hit
   with no adjacent quantifier fails. Report the exact term + location. *Hard.*
5. **L5 — `@risk` resolves**: every `@risk:<id>` matches an id in
   `docs/risk-register.md`. *Hard.*
6. **L7 — Open-question syntax**: every gap marker is exactly
   `# OPEN QUESTION -> PO: <text>`. *Hard.*
7. **L4 — Declarative steps**: no imperative UI verb (`click`, `tap`, `press`,
   `navigate to`, `scroll`, `select ... from ... dropdown`) in `Given`/`When`.
   *WARN* (mark FAIL only if pervasive; the semantic layer decides).
8. **L6 — Provenance format**: sourced lines match the citation format. *WARN.*
9. **L8 — Step-catalog preference**: near-duplicates of `steps/catalog.md`. *Advisory WARN.*
10. **L9 — AC budget**: count the payload's ACs (AC checklist items, or `Scenario`s
    with a `Scenario Outline` counting as one). More than 8 fails. *Hard.*
11. **L10 — Payload size**: measure the Jira description after wiki conversion
    (the `## Jira payload` section of `rewrite.md` when linting a rewrite).
    Over 20,000 characters fails (*Hard*); over 10,000 characters, or any AC
    checklist item over 250 characters, is a *WARN*. Report the measured numbers.
12. **Emit** a per-check result (pass / WARN / FAIL) with the exact offending text
    and line, and a single boolean: `hard_fail` = any of `L1,L2,L3,L5,L7,L9` failed
    or `L10` exceeded 20,000 characters.

## Output quality rules
- Every FAIL/WARN quotes the exact offending text and its location — no "some AC is vague".
- Deterministic: the same story yields the same result every time.
- This skill never rewrites or scores meaning; it only checks mechanics.

## Guardrails
- No stage ownership; `story-evaluator` owns the transition.
- If `hard_fail` is true, signal the evaluator to short-circuit to `GATE = FAIL`
  without semantic scoring (rubric "Overall gate", step 1).
- No invented requirements; this skill only flags, never fills gaps.
- When implemented as a script (see `scripts/`), any PowerShell must be ASCII-only
  (`AGENTS.md`).
