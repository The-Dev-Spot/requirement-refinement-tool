# User guide

For the complete standalone lifecycle, see `docs/standalone-workflow.md`.
Use a checkout with Python 3.11+ and the hash-pinned `requirements.lock` dependency.
The local-state controller requires POSIX permissions. It has no hosted service,
autonomous model loop or third-party write adapter.

## Validation and compatibility commands

- `python -m clarity validate-config`: validates the legacy prompt configuration.
- `python -m clarity lint <snapshot.json>`: executes machine checks; not semantic review.
- `python -m clarity benchmark examples/rule-benchmark.json`: 13 synthetic rule cases.
- `python -m clarity gate <report.json>`: legacy score-combination helper only.
- `python -m clarity work --help`: durable local lifecycle and capability authentication.

Exit 0 means the requested operation succeeded, 1 means a gate/check did not pass,
and 2 means input/authorization/storage validation failed. A successful `work review`
can legitimately return a NOT READY review: inspect its verdict/state. The legacy
`gate` helper cannot alter trusted workflow state or grant publication permission.

`.github/project-config.json` remains the strict prompt/legacy-helper template;
ignored `.github/project-config.local.json` can be explicitly selected for legacy
commands. Provider names are metadata, not functioning writers. Setting
writes_enabled to true is rejected. The v0.2 controller uses fixed documented
security ceilings and snapshot-selected risk/catalog inputs; it does not silently
load private MCP config or inherit broader permissions from an editor.

## Local Markdown evidence preview

`python -m clarity logbook RUN-demo --run-dir .clarity/runs/RUN-demo/1` retains the
legacy local Markdown-preview functionality. Default required files are
RUN-demo-run-summary.md, RUN-demo-quality-gates.md and RUN-demo-rewrite.md.
Missing required sections fail. The preview and SHA-256 manifest refuse overwrite
and do not represent a remote upload. The durable controller's sealed JSON export
is separate and includes its structured snapshots, reviews and decision records.

## Optional read-only Linear import

`python -m clarity linear-read DEMO-1 --team-id <team-id> --key-file <private-api-key-file>
--output issue-snapshot.json` reads only the selected issue and all retrieved
comment pages within its limits. An optional --project-id enforces project scope.
It does not create a run or infer missing requirements; inspect its scope/limitations
and transform the authorized evidence into a requirement snapshot explicitly.
No live account was used while implementing this adapter.

## Repository safety and evaluation limits

Stage only reviewed source, then run `python -m clarity check-repo`. That scanner
reads tracked working-tree files, not all historical Git objects or differently
staged bytes. Inspect and re-stage after changes. Never commit actual role keys,
SQLite state, backup files, private review HTML or imported issue snapshots.

The official parser is required in CI. Environments without network/package access
can run checklist/controller tests, but behavioral parser tests must be reported
as skipped rather than claimed to pass. Semantic model benchmarking, host-specific
smoke testing and live tracker validation are not replaced by unit test counts.
