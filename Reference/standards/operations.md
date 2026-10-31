# Reliability, observability and operational delivery

**Read:** asynchronous jobs, messaging, services, monitoring, incidents, scheduled workflows, deployments, high-throughput or production changes. **DoR:** D4/D5/D8/D9/D10.

## Sources

- [Google SRE Workbook — Implementing SLOs](https://sre.google/workbook/implementing-slos/) — use service-level indicators, SLOs and error-budget policies **approved by service owners**, not agent-generated "99.9%" numbers.
- [OpenTelemetry semantic conventions](https://opentelemetry.io/docs/specs/semconv/) — interoperable names for logs/traces/metrics and correlation across services. Version is evolving; verify with deployed collector/SDK.
- [NIST SSDF 1.1](https://csrc.nist.gov/projects/ssdf) — respond to vulnerabilities, protect release artifacts, track changes.
- [GitHub Actions security](https://docs.github.com/en/actions/how-tos/secure-your-work) — untrusted workflow/code and deployment boundaries.

## Challenge prompts

- **Failure and recovery:** What happens on timeout, cancellation, crash, partial commit, restart and duplicate event? Who can safely resume? How many retries before dead-letter?
- **Durability and idempotency:** Is there one authoritative work order and correlation key? Can event replay create duplicate issue, money transfer, PR or deployment?
- **Capacity:** What are worker-pool concurrency, CPU/RAM/disk/time budget and overflow behavior? Is `CRITICAL` status derived from trusted product registry or from an untrusted report?
- **Observability:** What signal proves success, stuck work or unexpected failure? Are release/version, incident/trace correlation and source timestamps captured? Can operators tell stale from current evidence?
- **Privacy/retention:** Are logs and traces scrubbed of secrets/PII and retained only under approved policy?
- **Operational ownership:** Who receives meaningful alerts? What is the rollback/forward-fix plan when needed, and does work require production approvals?
- **Performance:** If latency/availability matters, what real service objective is approved? Define measurement population/time interval before proposing thresholds.

## Forge City-specific test ideas

- Twenty accepted normal tickets cause **one Clarity normal and one Forge normal worker** at most; critical-only slots remain idle and unborrowed.
- A verified critical production issue uses dedicated Clarity/Forge critical workers while ordinary jobs continue. A pre-release app's user-submitted 'critical' tag cannot take those slots.
- A duplicated/replayed ticket results in one canonical issue and draft PR; worker restart never duplicates side effects.
- A provider-auth/usage interruption preserves queued work and reports `AUTH_REQUIRED` or `WAITING_FOR_QUOTA` without unbounded retries or silent API charges.
- A draft PR can be proposed without changing a production database, production config, deployment workflow or release state.

## Boundary

Clarity's role is to require *testable operational behavior*. It does not itself configure OpenTelemetry, deploy monitoring, set legal retention, certify SLOs or declare an end-to-end workflow complete merely because it can describe the workflow.
