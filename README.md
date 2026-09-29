# Clarity — excellent requirements, from any starting point

**Flexible input. One quality standard. Developer-ready output.**

Clarity is a standalone requirement-refinement product. A senior analyst, a junior
analyst and someone describing an everyday problem can start differently, but the
approved handoff must be equally clear, complete, consistent, faithful to the agreed
need and testable. Less complete input requires more assistance, not a lower bar.

**Gherkin is the canonical acceptance-criteria format.** The approved `.feature`
text is exported unchanged for development and test management, including an
explicitly selected Xray export profile. This is not a development-pipeline front
end, and it performs no tracker writes.

## v0.3: brief-to-handoff workspace

The `clarity.refine` workflow adds plain-language capture, decision-focused intake,
exact source quotations, operator-confirmed reference applicability, rule-to-scenario
coverage, independent claim/scenario review, bounded model assistance and an
interactive loopback workbench. It reuses the existing private SQLite workspace
and capability format, with separate additive tables for incomplete briefs.

A handoff contains the requirement, the **same approved Gherkin**, a traceability
matrix, selected evidence/decisions, the quality review and a hash manifest.
Only an operator can approve and seal it after independent review. Unresolved
business questions, unconfirmed proposals, unsupported statements and hard quality
failures cannot be waived into readiness.

## Start from a checkout

Python 3.11+ on Linux/POSIX is required for private controller state.

```sh
python -m pip install --require-hashes --only-binary=:all: -r requirements.lock
python -m unittest discover -s tests -v
python -m clarity.refine --state "$HOME/.local/state/clarity" init
```

Then follow the [refinement walkthrough](docs/refinement-workflow.md) to provision
separate author, reviewer and operator keys and start the workbench. Model use is
**disabled by default**. Optional Ollama assistance requires explicit model choices
and connects only to an operator-managed loopback endpoint; verify that the chosen
models actually run locally before submitting private material.

```sh
python -m clarity.refine --state "$HOME/.local/state/clarity" serve
```

Open the local address printed by that command. Without a model configured, an
analyst can import a structured draft/review through the same governed workflow.
No model availability or live-model quality is assumed.

## Product contracts

| Area | Implemented behavior |
| --- | --- |
| Raw input | Ordinary-language brief; no invented ACs, classification or completeness required at capture |
| Questions | Impact-ranked, one shown next; why the decision matters; stable IDs; authorized answers and explicit merge/scope resolutions |
| Evidence | Immutable source capture, exact quotation/hash checks, independent support judgments and recorded reference authority |
| Acceptance criteria | Official Gherkin parser/compiler, scenario IDs, context/action/outcome, outline/example checks, explicit rule coverage |
| Independent review | Separate capability, every statement and scenario reviewed, cold-read/counterexample challenge; no writer self-score |
| Approval | Exact source, policy, draft, review, export profile and file hashes; expiry, revocation and transactional local sealing |
| Workbench | Local forms, server-side sessions, CSRF/origin/Host checks, escaped text and no external page resources |
| Model execution | Opt-in bounded draft/question and independent-review stages; no tools, no approvals, no automatic retries |
| Evaluation | Same-need expert/partial/plain-input harness with per-group reporting and honest missing-output handling |

## What is not proven or implemented

Quotation verification is not proof that a claim follows from its source. Model
review is not proof of correctness or genuine independence. The synthetic tests
and parity fixtures do not establish equal real-world outcomes across user groups;
that needs repeated model runs and blind developer/tester review with human labels.

The workbench is a **single trusted local workspace**, not a public server, enterprise
identity system or multi-tenant service. Keep controller state and keys outside
agent access. Do not expose the listener through a tunnel or reverse proxy.
There is no live Xray/Jira publication, verified Xray round-trip, automatic test
implementation, automatic deletion, backup encryption or development-pipeline link.

Import only `acceptance.feature` into test management—not the evidence-bearing
handoff ZIP. `.feature` files specify tests; automation still needs step definitions.
Repeated external imports need a separately designed reconciliation strategy.

## Documentation

- [Operating contract](AGENTS.md), [handoff standard](docs/handoff-standard.md), and [Definition of Ready](rubric/definition-of-ready.md).
- [Refinement walkthrough](docs/refinement-workflow.md), [architecture](docs/architecture.md), and [security boundaries](SECURITY.md).
- [v0.3 implementation review](docs/review/2026-09-29-quality-handoff.md) and [next work](docs/roadmap.md).
- [Ten specialist roles](.github/agents/README.md) and [anonymization boundary](docs/anonymization.md).

The v0.2 `python -m clarity work` snapshot controller and its
[walkthrough](docs/standalone-workflow.md) remain for compatibility. Its checklist
snapshots and legacy exports are not automatically upgraded into the v0.3 Gherkin
handoff contract. The new `refine` APIs cannot approve or export a legacy snapshot.

The repository remains private. No original corporate history, proprietary corpus,
real operational records or credentials are included. No open-source licence is
granted by this change.
