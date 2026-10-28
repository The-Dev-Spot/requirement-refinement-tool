# Operational learnings

Generic operating rules only; no prior project episodes or run records.
Copy this register to the ignored working location before use.

| ID | Status | Reusable rule |
|---|---|---|
| L-0012 | active | Verify the configured comment renderer before choosing markup. |
| L-0014 | active | Use the configured artifact language; do not infer it from source language. |
| L-0018 | active | Traverse relevant child pages and data dictionaries before declaring a gap. |
| L-0020 | active | Resolve mention identities using the authorized connector; never guess account IDs. |
| L-0021 | active | Investigate related issues as precedent, explicitly distinguished from requirements. |
| L-0023 | active | Review scope, ownership, and provenance before prescribing a technical solution. |
| L-0024 | active | Use the connector-verified comment format and inspect the rendered result. |
| L-0025 | active | Every Jira write requires explicit operator approval for the staged outcome. |
| L-0026 | active | Review comments contain open questions only; findings and rewrites remain in evidence. |
| L-0027 | active | Confluence writes are limited to the explicitly configured log-book subtree. |
| L-0028 | active | Verify content-format and macro support against the actual connector. |
| L-0030 | active | Assemble evidence pages from full source files, without model summarization. |
| L-0031 | active | Re-read published evidence and verify completeness before recording success. |
| L-0046 | active | Use a project-specific classification field only after its mapping is verified. |
| L-0048 | active | Artifacts default to English unless the operator configures another language. |
| L-0049 | active | Request relevant fields explicitly; do not fetch every custom field routinely. |
| L-0050 | active | Independently verify attachments rather than relying on a success response. |
| L-0056 | active | Re-read after a comment timeout before retrying a potentially completed write. |
| L-0057 | active | Measure the final converted Jira description before writing it. |
| L-0070 | active | Warn above 10,000 description characters; fail above 20,000. |
| L-0082 | active | Keep build and verification facts in the lean payload; justify them in review evidence. |
