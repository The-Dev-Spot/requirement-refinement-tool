# NASA: writing a good requirement — adapted for Clarity

**Primary:** [NASA Systems Engineering Handbook, Appendix C — How to Write a Good Requirement](https://www.nasa.gov/reference/appendix-c-how-to-write-a-good-requirement/) (NASA/SP-2016-6105 Rev 2).
**Context:** [NASA Handbook §4.2 Technical Requirements Definition](https://www.nasa.gov/reference/4-2-technical-requirements-definition/).
**Source checked:** 2026-10-31. **Authority:** engineering guidance, not automatically binding NASA policy for unrelated teams.

NASA's Appendix C is a powerful **validation prompt**, not a demand to reproduce its checklist for every user story. Apply relevant checks to requirements, especially those being refined from vague defect tickets or spanning multiple services.

## Clarity's adapted NASA quality dimensions

| NASA theme | Ask of an individual story | Existing DoR mapping |
|---|---|---|
| Clarity and atomicity | One independently understandable intent or outcome? Ambiguous pronouns, `and/or`, `as appropriate`, or hidden context? | D1, D2, D3, D4 |
| Completeness | Actual/expected behavior, users/systems, inputs/outputs and necessary exception paths? Unknowns owned and explicit? | D1, D3, D5, D8, D9 |
| Consistency | Contradicts a parent requirement, deployed contract, established project decision or another story? | D6, D8, D9 |
| Traceability | Is there a justified owner/customer/mission need or approved parent; can this outcome be traced to tests and implementation? | D6, D8 |
| Correctness and feasibility | Is this feasible in actual constraints/platform? Does it wrongly prescribe a design without a confirmed reason? | D2, D6, D7, D8, D9 |
| Verifiability | What observable evidence proves satisfied, and what negative/counterexample disproves it? | D3, D4, D5 |
| Interfaces/data | Are relevant endpoints, events, fields, units, contracts and behavior between components unambiguous? | D9 |
| Reliability, performance and maintainability | Are meaningful degraded/recovery behaviors and quality constraints stated **when relevant** and measured? | D5, D10 |

### NASA's modal terminology — don't misapply it

In NASA-style system specifications, **shall** identifies a binding requirement; **will** often states facts or intent; **should** communicates a goal or preference. In Clarity's **agile** handover, preserve the adopted project format: behavioral `Given/When/Then` or nonbehavioral measurable outcomes. Do **not** impose literal `shall` on Gherkin steps, and do not assume all `should` statements are an accepted requirement.

### Requirements versus solution constraints

NASA distinguishes **what must be achieved** from **how it is implemented**. Challenge ungrounded technology prescriptions (e.g., "must use Redis") when the real need is idempotent processing. However, an owner-approved architecture, runtime, API or infrastructure constraint can legitimately constrain a story; preserve its source and rationale rather than discarding it.

### Precise verifiability, not invented values

NASA emphasizes objective demonstration, test, analysis or inspection, including performance values with defensible tolerances. Clarity must **not invent** percentages, latency SLOs, retry counts, accessibility targets, device specs or security controls to make a story superficially measurable. When needed, identify a proposed metric and open an owner question; leave `NOT_RUN` for unexecuted checks.

### Risk and safety nuances

NASA prefers positive requirement wording, but a **necessary prohibition** (e.g., no production changes, no cross-tenant access) is an important security acceptance criterion and must remain explicit. Distinguish operational procedures from system requirements, and use existing DoR D5 negative tests where appropriate.

## Practical NASA-informed quick review (run only applicable questions)

1. **Need:** Why is this change necessary? What customer symptom, parent objective or product policy supports it?
2. **Subject:** Which actor/component performs the outcome? Does it express **one** testable behavior rather than bundled unrelated work?
3. **Ambiguity:** Could two developers interpret words, states, numeric boundaries or interfaces differently?
4. **Conflict:** Does it contradict a newer project decision, existing API contract, sibling requirement or confirmed environment classification?
5. **Unknowns:** Which missing facts would change implementation? Mark `# OPEN QUESTION -> PO:` and the responsible decision owner rather than guessing.
6. **Verification:** What would demonstrably pass/fail? Which test, inspection, demo or analysis is possible in the receiving environment?
7. **Reliability:** If this touches async, failure, data or production behavior, are recovery, error handling, idempotency, traceability and safety boundaries adequately stated?
8. **Trace:** Is the requirement linked to its source and does the final AC test the actual need rather than merely a proposed design?

Do not produce an additional eight-item acceptance checklist. Use these to select the **2–5 most relevant questions**, update the existing D1–D10 findings, and keep the story payload within Clarity's AC budget.

## Example: customer defect → reviewed draft PR

**Unclear request:** "Fix the import issue quickly using whatever works."

**NASA-informed challenge:** Which app/version? Is the defect server-side? What input and response show failure? Is the duplicate known? What output is correct? What can be verified without deploying to production? What actual risk boundaries are approved?

**Illustrative measurable outcome** (only after owner confirms expected behavior): duplicate delivery of the same import event does not create duplicate canonical import jobs in the test backend, including after a worker restart. No production data is modified by the automated investigation. Client Unity/Android reproduction is **NOT_APPLICABLE** if only the backend is changed.

The source report and verified server behavior, not NASA's guidance, determine the product requirement. This source only helps Clarity discover missing questions.

## Source notes

- Appendix C spans correct modal terms, editorial quality, completeness, consistency, traceability, feasibility, interface/performance, maintainability, reliability, and verifiability checks. It is a **systems-engineering guidance checklist**, not a turnkey agile DoR.
- NASA §4.2 also discusses traceable requirements, design constraints, requirements metadata, parent/child relationships and the rationale for critical decisions.
- Don't copy lengthy NASA passages; use a short summary, exact source link and contextual applicability, recording the checked date in run evidence.
