# User guide

## Setup

Use Python 3.11+ from the repository root. No third-party runtime packages are
needed. Run `python -m clarity validate-config` and
`python -m unittest discover -s tests -v`. All examples are synthetic.

For a report smoke test: `python -m clarity gate examples/complete-report.json`.
Exit 0 means the reported-score combination is READY, 1 means NOT READY and 2
means invalid input. This command does not generate or verify the assessments.
An all-PASS synthetic fixture is not evidence of semantic accuracy.

For a review in an agent-capable editor, select story-orchestrator and provide
the requirement text. Select story-intake for a new requirement or story-creator
for a proposed breakdown. Follow `AGENTS.md`; no external issue is required for
local intake. Verify host tool permissions before use. No terminal or external
MCP tools are granted by the shipped profiles.

## Configuration

`.github/project-config.json` is a strict neutral template. Create ignored
`.github/project-config.local.json` for private settings and pass it explicitly
with `--config`. The only implemented integration is local processing; provider
names in configuration are reserved metadata, not functioning adapters. Live
writes must remain false. An empty MCP example configures no servers.

## Evidence preview

Create a run revision directory under `.clarity/runs/RUN-demo/1/`. The default
configuration requires `RUN-demo-run-summary.md`, `RUN-demo-quality-gates.md`
and `RUN-demo-rewrite.md`. Then run:

```sh
python -m clarity logbook RUN-demo --run-dir .clarity/runs/RUN-demo/1
```

The builder reads matching Markdown evidence, requires the configured inline
sections, calculates the union of exact open-question texts in the rewrite and
proposed comment, and produces a local page plus a SHA-256 manifest. It refuses
to overwrite previous outputs. A partial pair after interruption requires manual
reconciliation. It neither uploads attachments nor proves remote persistence.

## Repository safety

Stage only reviewed source files, then run `python -m clarity check-repo`.
The checker reads tracked working-tree files, not old Git objects or a differently
staged version. Re-stage and scan again after edits. Keep credentials, private
knowledge, operational logs, original archives and legacy Git history outside the
repository. Automated scanning is not a guarantee of complete anonymization.

## Known limits

Approval-plan checking is a library function, not a sign-in flow or publisher.
The caller must supply trusted identities, policies and source revisions. Replay
records are not stored atomically. No live model, Jira, Linear, Confluence or
GitHub publication has been tested or enabled. See the review and roadmap.
