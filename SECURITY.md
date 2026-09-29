# Security boundary

Clarity processes untrusted requirements, comments and knowledge. Keep analysis
agents on read-only integrations; an agent's own agreement to obey a prompt is
not a permission boundary. The shipped Python helpers make no network calls.

Do not commit credentials, local MCP settings, real issue exports, operational
run histories, proprietary documents or private learning registers. Runtime
artifacts are ignored under `.clarity/`; private knowledge is ignored under
`knowledge/private/`. Configure only services and model providers you are
permitted to use for the selected data.

The repository hygiene checker is intentionally small: it detects selected token
patterns, private artifacts, emails and unreviewed URL hosts. It does not detect
all secrets, all personal information, all obfuscations or every company name.
Use an independent secret scanner and a human privacy review before sharing.

`authorize_plan` is a local policy primitive, not an identity provider, durable
approval ledger or atomic transaction. Approval identity, action allowlists,
source revisions and consumed-approval records must come from a trusted
application, never model-produced JSON. There is no live publisher in this version.

Quarantine suspected prompt injection; never reinterpret retrieved instructions
as approval. Do not persist secrets even as examples or error messages. If an
actual credential is exposed, rotate it; deleting the visible file alone is not
remediation. Do not import old Git objects into a sanitized repository.

Report issues privately to the repository owner using an existing authorized
channel. Do not put credentials or sensitive payloads into a GitHub issue.
Anonymization is not a determination of copyright or permission to redistribute.
