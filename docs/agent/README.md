# docs/agent — runtime documents

This is the operational memory of a run. Agents read and write here as they take a
story through INVESTIGATE -> EVALUATE -> (REWRITE) -> VERIFY -> (PO ANALYSIS) -> APPROVAL. Write semantics (replace-in-place /
write-once / append-only / create-on-failure) are defined in
`../../.github/agents/runtime-doc-contract.yaml`, and ownership in `../../AGENTS.md`
("Docs Ownership").

Working registers and run folders are ignored by Git. Initialize missing registers
from `templates/registers/` on first run, preserving any existing private state.
Only neutral templates are tracked; keep actual project evidence private.

## Layout
- `run-status.md` — pointer to every run's status: active (awaiting approval) and closed.
- `runs-pruned.md` — durable ledger of closed-run folders deleted by `skill-run-cleanup`
  (story, date, bytes freed, log-book link) — the record that outlives the folder.
- `decision-index.md` — compact, scannable index of material decisions across runs.
- `learnings.md` — the single shared learnings register (lifecycle-managed).
- `templates/` — canonical structure for each run document. Copy, do not improvise.
- `runs/{story_id}/` — one folder per story (or `{spec_id}` for a creator run):
  - `run-context.md`, `story-input.md`, `detailed-plan.md`, `investigation.md`
    (INVESTIGATE stage), `eval-report.md`,
    `rewrite.md` (if a rewrite was needed), `quality-gates.md`, `handoff.md`,
    `decision-log.md`, `proposed-comment.md`, `error-report.md` (on failure).
  - creator runs additionally produce `breakdown.md`.
  - **Retention:** once a run **closes** (`done`/`rejected`/`failed`) *and* its
    evidence is verified published to the Confluence log book, this folder
    becomes eligible for deletion by `skill-run-cleanup` ("clean up closed
    runs") — never automatic, and never without a live-verified log-book page.
    See `../../.github/agents/runtime-doc-contract.yaml` (`retention:`). This
    keeps the repo's local footprint bounded as the number of processed
    stories grows; the log book remains the full audit trail and
    `run-status.md` + `runs-pruned.md` remain the permanent local index.

## Rules
- Use `{story_id}` from `run-context.md` for all paths.
- Never invent a date — read it from `run-context.md` (set at run start).
- Append-only files are never rewritten; replace-in-place files hold the latest state.
- Read `learnings.md` before setup/tooling decisions; append reusable candidates.
