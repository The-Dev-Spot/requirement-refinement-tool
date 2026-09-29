# Clarity — personal requirement refinement

Turn incomplete requests into evidence-backed, approval-ready requirements.
The north star is the **cold-read test**: can an unfamiliar developer build the
right thing without guessing?

This is the vendor-neutral personal baseline for The Dev Spot. It retains ten
agent roles and the investigation → evaluation → rewrite → verification → PO
challenge → approval workflow. It is **an agent toolkit plus offline Python
helpers**, not a hosted application, authenticated approval service, or a live
Jira/Linear publisher. No operational success claims from an earlier environment
are carried forward.

## Start

Python 3.11 or newer; no third-party Python packages are required.

```sh
python -m clarity validate-config
python -m unittest discover -s tests -v
python -m clarity gate examples/complete-report.json
```

The example report is synthetic and tests score combination only. The gate
command does not run a model, verify citations, or parse Gherkin.

In an agent-capable editor, read `AGENTS.md`, then use one of:

- `Review this requirement: <text>` or `Review DEMO-1` with an explicitly configured read adapter.
- `New requirement: <business problem>` for one-question-at-a-time intake.
- `Break down this specification: <text>` for proposed, individually evaluated stories.

Run artifacts belong in ignored `.clarity/runs/<run_id>/<revision>/`, not in Git.
Private grounding material belongs in ignored `knowledge/private/`. The shipped
configuration uses local mode and **disables all external writes**. Setting
`writes_enabled` to true is rejected because no live writer is implemented.

## Where to look

| File | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Canonical operating and approval contract |
| [Agent catalog](.github/agents/README.md) | Ten roles and entry points |
| [Definition of Ready](rubric/definition-of-ready.md) | D1–D10 and L1–L8 |
| [User guide](docs/user-guide.md) | Configuration, runs, evidence and limitations |
| [Architecture](docs/architecture.md) | Current toolkit versus intended product |
| [Review](docs/review/2026-09-29.md) | Findings, reproduced defects and remediation status |
| [Roadmap](docs/roadmap.md) | Prioritised implementation work and acceptance criteria |
| [Import boundary](docs/anonymization.md) | What was retained, generalised and excluded |
| [Security](SECURITY.md) | Trust boundaries and disclosure guidance |

## What runs today

`clarity/guardrails.py` validates configuration, combines complete reported scores,
counts canonical open questions, and checks exact publication plans against
application-supplied approval records. `clarity/logbook.py` builds local evidence
previews and hash manifests. `clarity/audit.py` checks tracked files for selected
credential patterns, private artifacts and unreviewed hosts.

These are tested primitives, not a complete security boundary. An unrestricted
agent could bypass a helper: give analysis agents read-only tools. Authentication,
atomic approval consumption, durable orchestration, external adapters, a complete
Gherkin linter and semantic evaluation benchmarks remain on the roadmap.

No deployment, imported credentials, proprietary reference corpus, legacy Git
history, or live customer/project records are included. No open-source licence
is granted by this baseline; confirm rights before any broader distribution.
