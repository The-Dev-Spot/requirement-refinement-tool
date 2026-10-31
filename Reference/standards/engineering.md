# Coding, API and data engineering standards

**Read:** code, API, service-to-service, event, data, migration, build or delivery stories. **DoR:** D3–D5, D8–D10 where triggered.

## Sources

- [OpenAPI Specification v3.2.1 (2026-09-10)](https://spec.openapis.org/oas/v3.2.1.html) — formal HTTP API contract. **Use the version adopted by the project**, not automatically the newest editor/toolchain version.
- [IETF RFC 9457](https://www.rfc-editor.org/rfc/rfc9457.html) — standardized HTTP problem details (obsoletes RFC 7807); adopt when suitable for a new or existing error format.
- [OWASP API Security Top 10: 2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/) — risks including object/property authorization, SSRF, resource consumption and unsafe external API use.
- [GitHub Actions security guidance](https://docs.github.com/en/actions/how-tos/secure-your-work) — workflow permissions and supply-chain safeguards.
- [NIST SSDF 1.1](https://csrc.nist.gov/projects/ssdf) — reviews, proven provenance, handling vulnerabilities and lifecycle policy.

## Ask only when relevant

### Code change and tests

- What is the exact observable defect/feature and target component? Is it a **behavior change**, a refactor, or a deployment contract?
- Does the existing style, module/interface layout, error handling and language/toolchain **already prescribe** the implementation? Don't force a generic library or architecture preference.
- What test verifies the intended behavior? Which negative/error/race/boundary scenarios matter? Identify `NOT_RUN` explicitly instead of implying all platforms passed.
- If this touches CI, is code from a fork or generated PR untrusted? Are credentials and production deployment routes excluded? Is least-privilege token scope tested?

### API and async/event consumers

- Specify method/path, request/response data, required vs optional fields, authentication/authorization, status/error semantics and compatible version/migration behavior.
- For events/jobs/webhooks: unique identity, at-least-once delivery implications, idempotency, deduplication, ordering assumptions, bounded retries/backoff, dead-letter handling, replay and operator recovery.
- When proposing a new error format, check whether RFC 9457 is appropriate; it is **not** a blanket mandate to replace an existing published API format.
- Consider per-user/object authorization, rate limits, payload size, pagination and PII/redaction where applicable. Avoid inventing numeric limits.

### Persistent data and migration

- Name canonical fields, types, units, ownership, cardinality, nullability and source-of-truth boundaries.
- What happens to existing records on migration? Is it reversible or forward-fix only? Are writes backward compatible during staggered rollouts? Is there a dry-run/backup/reconciliation requirement?
- Handle retries and failures without duplicated externally visible actions. Define privacy and retention only when grounded in owner policy.

## Suggested observable checks (adapt, don't copy blindly)

- An event replay/duplicate delivery produces **one** canonical work item and no duplicate PR.
- Unauthorized actor cannot access another user's resource; audit record and data are unaffected.
- A migration against seeded pre-existing records preserves accepted invariants; a failed migration has a documented recovery.
- A failed async job reaches a bounded recoverable state, with a visible reason and no infinite retry loop.
- A PR CI job cannot reach production secrets or deployment credentials when running untrusted code.

## Caveat

Clarity **specifies** what must be verifiable. It cannot claim static analysis, branch protection, workflow isolation or database migration succeeded without running the relevant authoritative checks in the correct environment.
