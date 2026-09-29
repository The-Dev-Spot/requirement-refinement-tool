# Security and data boundaries

Clarity processes untrusted requests, documents and model outputs. Requirements
must be excellent, but a polished answer is not evidence, authority or permission.
The repository remains private; do not import original corporate history, private
corpora, real operational records, credentials or identifying examples.

## Trusted local controller

Use a private POSIX workspace outside an untrusted agent's filesystem. Directory
0700 and file0600 checks reject symlinks and unsafe ownership. Capability secrets
are provisioned only by the OS-owner CLI; only hashes are stored in the database.
Author/reviewer/operator roles are fixed. An author cannot independently review or
approve the same draft. Authors cannot read other authors' briefs. Reviewers and
operators span the trusted workspace: this is not project/tenant isolation.

A process running as the controller's OS owner can read keys or alter code and
state. These controls do not sandbox that process. Never give an analysis agent
an unrestricted shell or operator key on that account. Separate identities do not
prove genuinely independent models; arrange real reviewer separation operationally.

## Local web workbench

The new server binds to 127.0.0.1 only. It enforces Host and POST Origin checks,
CSRF tokens, strict form parsing, bounded inputs, server-held expiring sessions,
HttpOnly SameSite=Strict cookies, logout, session rotation, escaped source content,
no external assets, restrictive CSP and no-store responses. It exposes no key
provisioning, arbitrary URL fetch, shell or policy administration route.

It uses local HTTP, not TLS, and is not an internet-facing production server. Do
not bind it publicly or place an internet reverse proxy in front of it. Local
malware, browser extensions and the OS owner are outside this boundary. It has
no enterprise SSO or multi-tenant authorization and must not be marketed as such.

## Models, evidence and approvals

Model calls are opt-in. The only implemented transport calls an explicitly chosen
Ollama model on loopback without redirects, proxies or model tools. Loopback does
not guarantee local inference; verify the model is not cloud-backed and that the
deployment is permitted to handle the selected data. Keys and sessions are never
included in model packets. Budgets and strict JSON validation are not isolation.
Credential-pattern checks reject known literal formats before model processing and
handoff, but are not comprehensive secret detection. Redact data before capture.

Captured references need operator-confirmed applicability; statements need exact
quotations and immutable source hashes. These establish recorded provenance, not
semantic entailment or independently verified remote authorship. Independent
statement/scenario review and human approval remain necessary.

Known instruction-pattern matches are review signals, not proof of an attack.
An operator can record a false-positive decision bound to a particular finding,
draft and context; changes invalidate that decision. A reviewer may explain a
context-sensitive wording/style warning. Neither can use that route to waive a
missing source, invalid Gherkin, incomplete coverage or other objective failure.
No clean scan, confidence score or user silence grants approval.

Approvals bind exact file hashes, revision, policy/context/review/engine versions,
profile and issuing credentials. They expire within 15 minutes. Revoked review or
approval keys block pending handoffs. Sealing and consumption are one transaction;
local idempotency is not remote exactly-once publishing. No remote writes exist.

## Recovery and disclosure

The versioned backup includes legacy and refinement records, not capability
secrets/hashes. It is NOT encrypted and can contain sensitive source material.
Keep it private with a separately retained digest. Restore into a new destination,
check integrity and provision new credentials. All old keys are disabled; pending
refinement handoffs need new independent review and approval. No automatic deletion.
Hashes detect corruption, not an attacker replacing both a backup and its receipt.

Handoff ZIPs contain source evidence and review records. Import only the approved
acceptance.feature into test management, not the full evidence-bearing ZIP, unless
you explicitly authorize that disclosure. Profiles are intended import targets;
no live Xray compatibility or remote privacy guarantee has been established.

The repository hygiene checker detects selected credentials, hosts and artifacts;
it does not find all personal information, identifying terms or encoded secrets.
Use independent scanning and human review before sharing. Rotate exposed real
credentials rather than merely deleting visible text. Report problems privately
to the repository owner; do not include sensitive payloads in public issues.
