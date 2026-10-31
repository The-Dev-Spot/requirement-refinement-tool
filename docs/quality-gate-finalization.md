# Clarity quality gate: finalization architecture and evidence rules

**Status:** implementation design and deterministic checker candidate, 2026-11-01. No unverified claim of production-ready autonomous quality assurance.
**Authority:** `rubric/definition-of-ready.md` D1–D10 and L1–L10. This document specifies execution and evidence, not a new rubric or compliance regime.

## Research basis

- [NASA Systems Engineering Handbook Appendix C](https://www.nasa.gov/reference/appendix-c-how-to-write-a-good-requirement/): individual requirements should be clear, complete, consistent, traceable, feasible and verifiable. **Project-wide contradiction detection is required**; polished text is not evidence of consistency.
- [ISO/IEC/IEEE 29148:2018](https://www.iso.org/standard/72089.html), still current per ISO's 2024 confirmation: requirements engineering and traceability. Do not reproduce licensed contents or infer organization-specific policy.
- [ISO/IEC 25010:2023](https://www.iso.org/standard/78176.html): product-quality model with nine characteristics. Use a **contextual quality attribute** selection under D10, not a global nine-item mandatory checklist.
- [Cucumber Gherkin reference](https://cucumber.io/docs/gherkin/reference/): formal Gherkin parsing and executable-step binding are different checks. A feature parse does not run any product tests.
- [OWASP ASVS 5.0.0](https://asvs.owasp.org/) and [NIST SSDF v1.1](https://csrc.nist.gov/pubs/sp/800/218/final): risk-scoped security quality and process evidence. No automatic security certification.
- [Google SRE Workbook — SLOs](https://sre.google/workbook/implementing-slos/): meaningful reliability targets have owners, populations and measured signals. Don't invent targets.
- [JSON Schema 2020-12](https://json-schema.org/draft/2020-12/): define machine-verifiable input/report schemas and reject unexpected fields when adding the future trusted runtime.

## The gate has three distinct executors

### A. Deterministic preflight — implemented as a local, **read-only** checker

Use `node .github/validation/quality-gate.mjs --input story.json --output report.json` after running `npm ci --ignore-scripts --prefix .github/validation`. An operator provides a **private** JSON input:

```json
{
  "title": "Example worker-pool reliability story",
  "story_type": "non-behavioral",
  "target_format": "markdown",
  "payload": "Objective: retain one normal and one critical-only worker per pool.",
  "criteria": [
    "One normal and one reserved critical worker per pool are active at maximum.",
    "A nonproduction issue never leases a reserved critical slot.",
    "After a simulated restart the same work order has one active lease."
  ],
  "review_notes": "> Source: Approved project decision, section Work Pools, last-modified 2026-10-31 (private review source)"
}
```

For `behavioral`, supply `feature` instead of `criteria` and use declarative `Given/When/Then`. The repository-pinned official `@cucumber/gherkin` parser is used to enforce L1, not a regex pretending to be a parser.

The output contains L1–L10 status, offending text, input SHA-256, `NOT_APPLICABLE` and `NOT_RUN` distinctions, hard failures, missing required checks, and **`ready_for_handover:false` unconditionally**. Mechanical `PASS` means only structural checks finished. No write to Jira, Linear, GitHub or production.

Cautions: L3's seed-word list is a **heuristic** and can over/under-detect vague terms; D4 must check meaning. L5 checks **only explicitly supplied risk IDs** against an approved register; it does not discover hidden risks (D5 does). L6 checks *citation format*, not source truth. L8 similarity is semantic and stays NOT_RUN until a real catalog/reviewer is present. L10 needs actual converted Jira wiki payload if `target_format=jira-wiki`; otherwise `NOT_RUN`. Native Linear Markdown is measured directly. A parsing success is not proof that step definitions exist, tests ran, or a code change works.

If a story cites a cross-project fact (e.g. "one global worker" versus current dual-pool policy), mechanical checks **cannot** establish consistency. That is a source-aware D6/D8 semantic finding, not regex keyword matching.

### B. Requirements evaluation — **not yet a certified autonomous runtime**

Independently invoked semantic evaluator examines the exact same frozen input SHA, project DoR adoption, approved risk register, authority-ordered decisions, source revision(s) and appropriate standards.

Required results:
- D1–D10 each has `PASS/WARN/FAIL/NOT_RUN` with exact evidence locator and rationale; trigger-aware D9/D10 escalation (interface / personal data / security / safety / regulated flow).
- NASA quality cross-read: atomicity, ambiguity, necessity, consistency against current governing decisions, contradictions to parent/other approved stories, source and bidirectional AC/test trace.
- D5 *discovers* risks beyond explicit tags using the project risk register; empty/unapproved risk policy is `NOT_VERIFIED`, never assumed safe.
- D6 grounds any numerical threshold, policy or target. Missing owner decision is `# OPEN QUESTION -> PO:`, not fabricated acceptance criteria.
- For project policy conflicts, record exact source revision and priority; do not silently treat "latest paragraph" as permission to overwrite an official ADR.
- Scope-aware checks: backend defect should not be required to pass Unity/Android UI tests; client UX must address actual states and adopted accessibility goals.
- Keep 3–6 ACs, max 8; prefer consolidation/splitting over adding a checklist item for every source.

The current toolkit has **agent prompts**, not a guaranteed independent evaluator service. A reviewer calling itself "independent" in a JSON payload is not proof of separate invocation. Actual runner provenance and model/tool evidence must be trusted by a supervisor.

### C. Independent challenge/recheck — **still to be implemented/qualified**

Give a second reviewer a clean copy of the original source and final candidate story, plus the authoritative policy/version index **but not the first evaluator's verdict**. Ask it to find counterexamples and missing requirements. The supervisor (not the reviewing model) binds reviewer identity/run, input hash, source revision, decisions and evidence to a result. Compare the two verdicts; disagreement or an unaddressed blocking finding becomes `BLOCKED`, not an average score.

The independent reviewer must specifically test:
1. Can two teams implement different outcomes from this story?
2. Has an older requirement survived alongside a newer contradictory approved decision?
3. Are the most damaging failure/permission/rollback paths measurable?
4. Did the draft invent technology choices, user expectations, thresholds or legal duties?
5. Is the intended acceptance type correct, and can Forge trace each AC/scenario to a measurable test oracle?
6. Does the security/prod boundary preclude indirect mutation through CI and automation?

An LLM-only synthetic reviewer cannot attest to executed tests or source correctness. Source freshness, actual model prompts, refusals, retrieval, token usage, different model sessions and reviewer independence must be recorded.

## Aggregation and status rules

| Condition | Status and consequence |
|---|---|
| Any hard L1/L2/L3/L5/L7/L9/L10 FAIL | **FAIL**; do not spend model tokens evaluating a mechanically invalid artifact |
| Required deterministic check NOT_RUN, source unavailable, missing risk-policy authority, missing independent reviewer or conflicting approved decisions | **BLOCKED** / NOT_VERIFIED; never READY |
| Semantic hard D dimension FAIL | **FAIL** |
| Reviewer disagreements, open product questions, unresolved D warnings | **WARN / BLOCKED**; needs decision, not a false PASS |
| All mechanical checks executed (excluding documented N/A/advisory), all D1–D10 PASS, no outstanding decisions, independent review pass with genuine run evidence and source binding | **READY candidate**; operator/team publication policy still controls writes |

`BLOCKED` is an *execution/verification status*, not an eleventh DoR dimension. It means a readiness decision cannot yet be established. A finding with no executed checker/verified source must not be given `PASS`.

## Regression and calibration corpus

Keep **real customer/organization/project content private**. Public repo may contain fictional regression examples; secured evaluation runs may read actual Forge City M0 issues read-only.

| Case | Expected gate behavior |
|---|---|
| A complete M0 research/enabler checklist | Mechanical PASS; semantic/independent verification still pending |
| `HOM-1972` historical one-global-worker vs newer 2 × (normal+critical) architecture | Semantic consistency blocker with both authoritative source references, proposed resolution, no invented assumption |
| M0 security threat-model issue | D5/D10 asks for trust boundaries, privilege and negative test evidence; no blanket ASVS mandate |
| Backend-only defect with no UX change | UX/client standards NOT_APPLICABLE |
| Behavioral feature with malformed Gherkin or missing Given/When/Then | L1 FAIL using official parser |
| Eight ACs then ninth added | L9 FAIL |
| Blank risk register and risk-relevant story | D5 NOT_VERIFIED or BLOCKED; L5 syntax alone is not a PASS for risk completeness |
| Unsupported performance target invented by model | D6 hard question / fail pending verified source |
| Fake reviewer "PASS" without actual runner | BLOCKED |
| Schema-valid Clarity → Forge handoff with unrun tests | PASS for format only, product verification NOT_RUN |

For a meaningful **before/after** comparison, freeze identical original issue revisions, project policy snapshot and execution conditions. Measure independently annotated true blockers caught, false alarms, missed material requirements, contradictions caught, source hallucination, unjustified AC growth, evaluator disagreements, elapsed time and token spend. No percentage-improvement claim without observed figures.

## Work left to qualify as complete

1. Wire direct Linear/GitHub/pasted-source intake into a **read-only, logbook-optional** orchestrator; keep project references out of the public generic repo.
2. Supply a real execution-backed independent reviewer that produces trusted run IDs/source hashes; distinguish independent invocation from prompting multiple personas.
3. Add versioned structured schemas and an aggregator with fail-closed identity/provenance checks; a supplied JSON label is not authentication.
4. Run the seven current M0 issues (start with HOM-1943, HOM-1945, HOM-1972); independently review results and measure actual precision/recall vs known introduced faults.
5. Publish a project-approved local DoR/risk-policy overlay, then decide whether Clarity's *own* output satisfies it. A globally unratified DoR cannot be silently promoted to project policy.
6. Only after those pass, allow a trusted Forge City WorkOrder to consume Clarity's typed handoff for draft-PR generation. No authorization/criticality/production rights in portable metadata.

**Non-goals:** auto-post to trackers, auto-merge, production deployment, running a model in CI, or replacing Forge's governed test/verification stages.
