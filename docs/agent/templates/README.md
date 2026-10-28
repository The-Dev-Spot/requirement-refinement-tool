# Run artifact templates

Create files under ignored `.clarity/runs/<run_id>/<revision>/`, prefixing each
artifact name with the stable run ID, for example `RUN-demo-rewrite.md`.

| Artifact | Required content |
| --- | --- |
| run-context | run ID, revision, mode, owner, source ID/revision, configuration digest, language, budgets |
| story-input | immutable source/transcript snapshot, retrieval time, separate ACs, comments and source locator |
| investigation | scope, inspected sources/versions, confirmed facts, conflicts, missing evidence and citations |
| eval-report | D1-D10 and L1-L8 scores with rationale, applicability and evidence; unknowns remain NOT_RUN |
| rewrite | beneficiary/objective/value, scope/exclusions, ACs, risks, contracts, citations and open-question markers |
| quality-gates | independent reviewer, final revision/digest, findings, verdict and evidence |
| proposed-comment | owner questions with stable IDs; no implied description or field update |
| po-analysis | question ID, source answer, authority, confidence category and unresolved remainder |
| po-challenge | question ID, keep/sharpen/merge/drop/propose decision, rationale and ID mapping |
| po-responses | author authority, comment ID/date, answer, interpretation, conflicts and resulting revision |
| decision-log | append-only decision ID, time, actor role, evidence and rationale |
| handoff | append-only stage transition, input/output hashes, owner and pending actions |
| run-summary | current state, final verdict, unresolved IDs, approval/publication status and next owner |
| breakdown | proposed slices, source coverage matrix, dependencies, per-slice verdict and unanswered questions |

Store reported statuses separately as `evaluation.json`, using the example
schema but not copying its PASS values. Store the exact proposed action list and
payload in `publication-plan.json`; its existence is not approval. Preview and
manifest files are derived artifacts and must not overwrite prior revisions.
