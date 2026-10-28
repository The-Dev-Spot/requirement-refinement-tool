# Security

Clarity runs as one trusted local workspace. The server binds to `127.0.0.1` and
requires its exact Host and Origin for mutations, server sessions, CSRF tokens and
escaped content. It loads no external page resources. Do not expose it through a
public tunnel or reverse proxy.

## Roles and authority

The author captures and drafts. A different reviewer checks meaning and coverage.
The operator configures policy, confirms decisions and source applicability, and
approves the exact handoff. Login keys are revocable capabilities, not enterprise
accounts. An assistant receives only an author or reviewer key through its local
MCP server. The bridge restricts tools to one selected requirement; it has no
operator, shell, provisioning, arbitrary URL fetch or remote-write tool.

These are application boundaries. They do not sandbox a coding assistant running
under the same OS user. Review your client's file/tool permissions and keep the
operator key and private controller state outside its accessible workspace.
Do not attach an operator key to an assistant.

## Credentials and data

Service credentials are encrypted with Fernet using an owner-only `vault.key`.
The database, key and state directory require POSIX ownership and private modes.
The UI receives only configured/not-configured metadata; saved credentials never
appear in model packets, page fields, exports or request logs. The local vault is
not an OS-keyring integration and does not protect against the OS owner or an
attacker who can read both database and key.

Model calls are explicit, bounded and never retried automatically. Local inference
is restricted to a selected loopback port; verify that the service does not forward
to a cloud model. Optional cloud adapters use fixed HTTPS hosts and require an
explicit sharing switch. Source adapters enforce configured scope and reject
redirects. Source locators are labels and are never fetched as arbitrary URLs.

Source text is untrusted data. Exact quotation checks do not prove entailment.
Independent review and operator decisions remain required. Suspicious instruction
signals remain visible; objective blockers cannot be waived.

## Backups and sharing

`clarity backup` creates a passphrase-encrypted backup and excludes login keys,
service credentials and the vault key. Keep the digest receipt separately and test
a restore. Restoring disables old login keys, invalidates unsealed approval and
requires reconnection to services. There is no automatic retention pruning.

A handoff ZIP contains selected source material. Share only the files appropriate
to the recipient. See [data hygiene](docs/data-hygiene.md). The generic scanner
helps detect credential-like literals and unexpected hosts; it is not a privacy
proof or a full secret scanner.

Report a suspected issue privately to the repository maintainer, with minimal
reproduction steps. Do not put credentials or private evidence in an issue.
