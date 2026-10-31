# Requirements, acceptance criteria and test evidence

**Read:** any new, reviewed or defect-derived story. **DoR mapping:** D1–D8, D9/D10 where triggered.

## Research anchors

- [ISO/IEC/IEEE 29148:2018](https://www.iso.org/standard/72089.html) — requirements-engineering processes; publicly available *abstract* and publisher metadata. Current edition confirmed by ISO in 2024; replacement in development. **Do not reproduce its licensed clauses**, or assert a clause-specific rule without access.
- [NIST SSDF 1.1 / SP 800-218](https://csrc.nist.gov/projects/ssdf) — secure-development process evidence and preparing, protecting, producing and responding to vulnerabilities.
- [DoR](../../rubric/definition-of-ready.md) — Clarity-specific **working-draft** readiness contract and AC format (primary local authority).

## Challenge questions

1. What concrete outcome and affected user/system are intended? What is **out of scope**?
2. Can a new developer identify target repo/component, observed vs expected behavior, exact constraints and dependencies without consulting a private conversation?
3. What existing requirement, incident, product decision, contract or test **supports** the claimed behavior? Are we confusing a sibling precedent with a confirmed requirement?
4. What is the smallest proof that fails before and passes after the proposed change? Include a relevant negative/permission/failure case if risk demands it.
5. What data/platform/environment assumptions are unverified? Who can decide them? An unsupported numeric SLO, accessibility target or retention period must be a question, **not invented**.
6. Are the acceptance criteria **observable at the interface** (behavioral Gherkin) or **measurable engineering outcomes** (non-behavioral checklists)? Is any criterion actually a dependency of a different story?
7. For a customer-reported defect: is the duplicate fingerprint/previous fix known? Which app/release is affected? Does `CANNOT_REPRODUCE` lead to a truthful disposition rather than a fabricated `PASS`?

## Evidence and gate interpretation

- Good: `Given an unauthenticated caller, when GET /private/orders/123 is requested, then the service returns the documented unauthenticated response and does not disclose order data` — provided the desired policy/response has been confirmed by the owner.
- Bad: `Make the service completely secure and highly available` — untestable and assumes a 100% guarantee.
- Semantic review can identify a missing concern; **it does not prove a test executed**. Evidence records exact runner/tool, target version, timestamp and result, or `NOT_RUN`.
- If a requirement is absent in the authoritative project documents, raise `# OPEN QUESTION -> PO:` rather than forcing an industry recommendation into the story.
- Preserve DoR L1–L10 and D1–D10; this document adds **no extra universal quality gate**.

## Reference to DoR

Use `D1` for hidden context, `D3/D4` for missing/unmeasurable ACs, `D5` for relevant negative cases, `D6` for invented facts, `D7` for overlarge stories, and `D8` for blocking prerequisites.
