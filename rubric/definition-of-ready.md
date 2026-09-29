# Definition of Ready

Standalone rubric v1; semantic judgments remain reviewer responsibilities. The north star is the cold-read
test: could an unfamiliar developer build the intended outcome without guessing?
These identifiers preserve the original review dimensions. No project-specific
custom field determines the type of work in this baseline.

## Story types

Behavioral work uses declarative Given/When/Then acceptance criteria describing
observable outcomes, including relevant error cases. Non-behavioral research,
enablers and infrastructure work use measurable outcome checklists. Classify
from the requested outcome, not the presence or absence of a custom field.
A checklist must still let a reviewer decide whether each outcome is achieved.

## Dimensions

| ID | Assessment | Weight and passing evidence |
| --- | --- | --- |
| D1 | Cold-read independence | Hard: terminology, rules and accessible context are explicit. |
| D2 | Story shape and value | Hard: beneficiary, objective and reason are specific. |
| D3 | Appropriate acceptance criteria | Hard: testable behavioral scenarios or measurable non-behavioral outcomes. |
| D4 | Precision | Hard: observable results, quantified limits and unambiguous conditions. |
| D5 | Risk coverage | Hard: applicable risks have traceable negative/failure outcomes. |
| D6 | Provenance and no invention | Hard: sourced claims carry evidence; unknowns remain open questions. |
| D7 | Scope and sizing | Soft: independently valuable slice with explicit exclusions. |
| D8 | Dependencies and assumptions | Soft: prerequisites, sequencing and assumptions are visible. |
| D9 | Data and interface contracts | Soft, hard when an interface is touched: schemas, errors and compatibility. |
| D10 | Non-functional and compliance requirements | Soft, hard for regulated work: measurable security, privacy and operational constraints. |

Use PASS, WARN or FAIL with rationale and evidence. Record NOT_RUN when a check
was not performed; never use PASS to mean unavailable. For an inapplicable
criterion, a reviewer must record the applicability rationale rather than silently
omitting the dimension. Model judgments require human review for material risks.

## Linter/check contract

| ID | Check | Severity |
| --- | --- | --- |
| L1 | Valid Gherkin syntax for behavioral ACs; appropriate measurable checklist otherwise | Hard |
| L2 | Valid project tag syntax; recognized namespaces | Hard |
| L3 | No unquantified vague acceptance terms | Hard |
| L4 | Declarative behavior rather than UI click instructions | Advisory |
| L5 | Risk references resolve to the selected risk register | Hard |
| L6 | Provenance format contains source, section, source date and locator | Advisory |
| L7 | Exact open-question marker syntax | Hard |
| L8 | Prefer established canonical step wording | Advisory |

The standalone runtime runs L1-L8 through `clarity/lint.py`. L1 uses the pinned
official Gherkin parser/compiler, or a structured outcome checklist with an explicit
`| Verify:` method. L2 checks risk/type/scope tag namespaces; L3 uses a finite
English vagueness vocabulary; L4 flags common UI choreography; L5 checks selected
risk IDs; L6 checks structured provenance presence (schema validation checks its
fields); L7 validates exact question markers; L8 compares against an explicitly
selected catalog, when present. These are scoped machine rules, not a complete
semantic linter. Non-English lexical checks remain NOT_RUN. Missing parser means
NOT_RUN. Preferred narrative ordering is not the same thing as grammar validity.
The legacy `gate` command still only combines supplied scores and cannot modify
trusted run state. A passing syntax check does not verify outcome measurability,
citation truth, applicability or business correctness.

Exact marker on its own line: `# OPEN QUESTION -> PO: <specific question>`.
Use stable question IDs in run records; text deduplication is only a helper.
Risk tags use `@risk:RISK-001`; project risks must be reviewed before use.
A source citation records title, section, original modified/effective date and
locator. Track retrieval/conversion time separately from source validity.

## Combination

Any hard FAIL produces FAIL. Otherwise any non-PASS status, unresolved question
or unconfirmed proposal produces WARN. Only a complete all-PASS report without
questions, proposals or injection concerns becomes READY. D9 escalates for
interfaces; D10 escalates for regulated work. READY never authorizes publication.
See `clarity/guardrails.py` and `tests/test_guardrails.py` for executable rules.
