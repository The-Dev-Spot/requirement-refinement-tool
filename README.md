# Clarity — standalone requirement refinement

Turn incomplete requests into evidence-backed, independently reviewed requirements.
The north star is the **cold-read test**: can an unfamiliar developer build the
right thing without guessing?

**v0.2 is a local-first standalone workflow**, not the front end of a development
pipeline. It combines ten agent role definitions with a durable, capability-
authenticated controller, executable rule checks, a read-only review workbench,
and approved local exports. There is no hosted service or autonomous model runner.

## Start

Use a repository checkout on Linux/POSIX with Python 3.11 or newer. Windows
private-state support is intentionally rejected until its ACL model is implemented.

```sh
python -m pip install --require-hashes --only-binary=:all: -r requirements.lock
python -m clarity validate-config
python -m unittest discover -s tests -v
python -m clarity lint examples/checklist-requirement.json
python -m clarity benchmark examples/rule-benchmark.json
```

The third-party runtime dependencies are the pinned official Gherkin parser
and its typing-extensions dependency.
Without it, behavioral syntax checks return NOT_RUN. The fixture benchmark tests
13 synthetic rule cases, not model accuracy or real-world semantic correctness.

For a durable workspace and authenticated review/approval flow, follow the
[standalone walkthrough](docs/standalone-workflow.md). `python -m clarity work --help`
lists the controller commands. Keep its state and keys outside an agent workspace.

## What now works

| Capability | Implementation |
| --- | --- |
| Durable runs and resume | SQLite transactions, immutable revisions, append-only hashed events, optimistic version checks |
| Role separation | Revocable author, reviewer and operator capabilities; one fixed role per actor; run ownership |
| Independent review | Digest-bound D1-D10 rationale/evidence; L1-L8 recomputed by the application |
| Owner questions | Stable IDs, authenticated answers, mandatory revised incorporation and re-review |
| Approval | Exact local export plan, policy/source/review hashes, expiry and credential revocation |
| Duplicate prevention | One active run per source/project; atomic single-consumption approval and sealed export |
| Evidence and recovery | Self-contained exports, integrity checks, explicit backup/restore with old keys disabled |
| Inputs | Local Markdown snapshots and an optional bounded read-only Linear issue/comments adapter |
| Review workbench | Escaped offline HTML with source diff, evidence, questions, rule results, exact plan and audit trail |
| Regression checks | Positive, negative, concurrency, corruption/recovery, adapter and parser tests |

## Boundaries

This release publishes **only to its local immutable export store**. No Jira,
Linear, GitHub issue or Confluence mutation, automatic retention deletion,
software-development pipeline integration or production deployment is included.
Read-only Linear imports have contract tests but have not been exercised against
a live account in this implementation session.

Capability checks protect the API from unauthorized operations; they do not stop
a process that owns the database or can read the operator's keys. Use a trusted
controller account and scoped submissions. The current CLI is not a network
security boundary or enterprise identity provider. The static workbench cannot
perform writes or approvals. Model orchestration remains in the chosen editor;
no claim of an unattended autonomous refinement engine is made.

## Documentation

| Document | Purpose |
| --- | --- |
| [Operating contract](AGENTS.md) | Canonical behavior and trust boundaries |
| [Standalone walkthrough](docs/standalone-workflow.md) | Setup, full run, decisions, exports and recovery |
| [Agent catalog](.github/agents/README.md) | Ten preserved roles |
| [Definition of Ready](rubric/definition-of-ready.md) | D1-D10, executable checks and semantic limits |
| [Architecture](docs/architecture.md) | Controller, adapters, storage and host boundaries |
| [User guide](docs/user-guide.md) | Compatibility helpers and operational limits |
| [Hardening record](docs/review/2026-09-29-hardening.md) | Delivered changes and validation scope |
| [Original review](docs/review/2026-09-29.md) | Historical baseline findings |
| [Roadmap](docs/roadmap.md) | Remaining standalone product work |
| [Import boundary](docs/anonymization.md) | Neutral source and excluded private material |
| [Security](SECURITY.md) | Threat model and known limitations |

The repository remains private. No original corporate history, private reference
corpus, operational run records or credentials are included. No open-source
licence is granted; anonymization is not a determination of reuse rights.
