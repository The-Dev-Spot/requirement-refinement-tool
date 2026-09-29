# Security boundary — standalone v0.2

## Protect the controller, not just prompts

Keep the controller database, installed source and capability keys outside the
agent workspace. The shipped agent profiles do not receive terminal, tracker-write,
operator-key or provisioning permissions. A process with the controller's OS
account can read its keys or rewrite its database/code; application role checks
cannot sandbox that process. No protected network API or enterprise sign-in ships.

Local capability keys are random 256-bit secrets stored only as hashes in SQLite.
The API enforces author/reviewer/operator roles, stable actor roles and author
ownership; identity means possession of an operator-provisioned capability, not
proof of a person's legal identity or an enterprise account. Provision separate
reviewer identities deliberately; aliases alone do not produce independent review.
Provisioning is trusted OS-owner administration and must not be exposed to agents.

Use owner-only POSIX state directories (0700), files (0600), no symlinked ancestors,
and a trusted local filesystem. Windows is rejected until proper ACL handling
exists. Keys never belong in source, prompt text, command arguments or ordinary
logs. The CLI accepts private credential files and does not print their contents.
Revocation invalidates access and the issuing key's unused approvals.

## Approval and data integrity

An independently reviewed READY artifact is not permission to publish. Operators
approve exact displayed plans bound to current snapshots, source/review hashes and
policy fingerprints. Approvals expire within 900 seconds; changed revisions,
answers, reviews, policies or credential status invalidate them. Sealing and
approval consumption are atomic and repeatable without duplicate exports.
Only local artifact sealing exists. No remote tracker mutation is enabled.

Append-only events and immutable revisions have integrity hashes and SQL guards.
These detect accidental corruption; they are not tamper-proof against a privileged
owner. Backups contain private evidence but no authentication hashes/secrets.
Protect and encrypt backup files separately. Restore requires a new workspace,
verifies its retained digest, disables old keys and revokes unused approvals.
Automatic deletion and external retention jobs are not implemented.

## Evidence and adversarial input

Requirements, comments, source documents, model assessments and learned rules are
untrusted data, not tool instructions. Known suspicious instruction patterns flag
a run for sticky quarantine. A clean scan is not proof of safety. The operator
must inspect a clean revision before release; fresh independent review follows.
The detector is heuristic and can miss obfuscation or non-English attacks.

Machine checks cover grammar and selected deterministic/lexical rules. They do
not verify semantic truth, source authority, relevance or every possible vague
requirement. Evidence references must resolve inside the submitted snapshot;
authenticity still needs review. No real-world semantic-accuracy claim is made.

The optional Linear importer uses one fixed HTTPS endpoint, read queries only,
explicit team/project checks, bounded pagination, conservative error handling
and no credential-bearing redirects. Use a team-restricted read-only key. The
adapter has mocked contract tests, not a live integration certification.
The offline workbench escapes data and forbids network/script/form activity;
it is a static private snapshot, not a write-capable web application.

## Source hygiene

Do not commit private documents, real exports, runs, original archives, prior Git
history, local MCP configuration, secrets or credentials. The small repository
scanner is not a complete secret/anonymization tool. Perform human review and
an independent scanner pass before broader distribution. Rotate an exposed key;
deleting visible content does not remove prior exposure.

Report security issues privately through an existing authorized owner channel.
Never put secrets in public issues. Keep the repository private; anonymization
does not establish ownership or redistribution rights.
