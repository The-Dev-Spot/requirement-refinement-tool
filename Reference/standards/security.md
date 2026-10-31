# Security, privacy and AI-agent trust standards

**Read:** auth, accounts, APIs, personal information, sensitive data, public-facing services, agents, tool-connected workflows, hosted CI, or production operations. **DoR:** D5/D6/D9/D10, severity depends on story risk and DoR escalation rules.

## Publisher references (reviewed 2026-10-31)

- [OWASP ASVS **5.0.0 stable**](https://asvs.owasp.org/) — testable controls for web apps/services. Reference the specific stable `5.0.0-<id>` only after consulting its versioned control data; don't use bleeding edge as a release gate.
- [OWASP API Security Top 10: 2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/) — risk discovery for external/internal APIs; **risk awareness**, not a substitute for ASVS controls.
- [OWASP MASVS](https://mas.owasp.org/MASVS/) — mobile security. Match platform and risk profile; don't apply native device controls to server-only work.
- [OWASP LLM Top 10: 2025](https://genai.owasp.org/llm-top-10/) — prompt injection, sensitive disclosures, insecure downstream handling and excess agency; separate review from app-layer risks.
- [NIST SP 800-218 SSDF 1.1](https://csrc.nist.gov/projects/ssdf) — secure development process, safeguards and handling known vulnerabilities.
- [European Commission: privacy/data protection by design/default](https://commission.europa.eu/law/law-topic/data-protection/information-business-and-organisations/obligations_en) — minimize personal data, purpose/scope, access, retention. Consult legal/privacy owner for actual jurisdictional duties.

## Challenge by trust boundary

| Trigger | Questions to raise | Verification candidate |
|---|---|---|
| Authentication/session | Who is the principal? What if missing, expired, revoked, replayed? | anonymous, expired and revoked access denied without leakage |
| Authorization/multitenancy | Can tenant A access tenant B's object/field/action? | cross-user/object test; object- and function-level permissions |
| External input/file/webhook | Are origin, signature, bounds, format, replay, URL allowlist and injected instructions checked? | forged/replayed payload rejected, no side effect |
| Secrets/credentials | Where are credentials injected and rotated; who can read them? | no secret in prompts, output, CI artifacts or logs |
| Data processing | Is personal data necessary? Who can view it, and how long retained? | redacted issue/trace/PR and approved retention evidence |
| Software supply chain | Can untrusted PR change CI, deployment, action permissions or signing keys? | isolated CI, short-lived token and negative escape test |
| AI agent → tools | Who grants authority? Does untrusted ticket/log override instructions or permissions? | prompt injection cannot change tool scope; no self-approval |
| Mobile native work | Is device storage, network, auth and tamper/privacy posture relevant? | choose MASVS profile and specific tests; otherwise N/A |

## Fail-safe design for Clarity → Forge support automation

- Ticket descriptions, stack traces, external web pages, Jira/Linear/GitHub comments and agent-generated code are **untrusted input**. They cannot select a repository, escalate `CRITICAL`, alter a tool allowlist, or authorize deployment.
- Source acceptance by n8n can preauthorize **bounded investigation and draft PR**, never direct production mutation. Production reads must be authorized and narrowly scoped to sanitized server diagnostics.
- Separate identities for tracker issue writer, Forge code workspace, PR publisher and production operator. Issue writes do not convey release rights. Approval must bind to actor + exact artifact/action + revision.
- Keep submitted PRs **draft-only** until independent CI/security review and human release controls. Never use untrusted PR workflow execution on a privileged production runner.
- Don't assert "secure", "zero-risk", "GDPR compliant" or specific ASVS level without matching scoped audit and verification evidence.

## Where to place findings

Use an **existing** relevant DoR dimension. A plausible exploitation path belongs under D5 (and its negative outcome); uncertain legal or data handling facts under D6/D10; missing auth/API contract under D9. A risky missing policy is a PO/security question rather than a model-generated command.
