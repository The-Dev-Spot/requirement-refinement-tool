# Skill: skill-run-cleanup

## Purpose
Prune the local `docs/agent/runs/{story_id}/` folder for runs that are **closed**
(`done` / `rejected` / `failed`) once their full evidence set is confirmed safely
externalized to the Confluence **log book** (`skill-confluence-log`). Without this,
the repo's local run-doc footprint grows without bound as more stories are
processed — every run writes 10-14 markdown files, several of which
(`run-context.md`, `eval-report.md`, `quality-gates.md`) get rewritten multiple
times per run. The log book already carries the complete audit trail (every raw
`.md` file attached, per `confluence.log_book.attach_evidence`), so once that
publish is verified, the local copy is redundant.

> **This is a local repo-hygiene operation, not a Jira or Confluence write.** It
> never touches Jira. It never edits a Confluence page (it only *reads* the
> already-published log-book page to verify it). Read access is broad; the only
> write is deleting local files and updating `run-status.md` / the prune ledger.
> It still follows this toolkit's verify-before-destructive-action discipline:
> **never delete a run folder without first confirming its evidence is safely
> published elsewhere.**

## When to invoke
- Operator command: **"clean up closed runs"** (or "prune closed runs") to
  `story-orchestrator`, which invokes this skill. Not automatic — closing a run
  makes it *eligible*, it does not trigger an immediate deletion. Run this
  periodically (e.g., whenever `docs/agent/run-status.md`'s Closed runs table
  has grown) or whenever repo size becomes a concern.

## Reads
- `docs/agent/run-status.md` — the **Closed runs** table (candidates live only
  here; active runs in the other two tables are never touched).
- `docs/agent/runs/{story_id}/{story_id}-logbook.md` for each candidate — the
  Confluence page id/URL recorded when evidence was published.
- `.github/project-config.yaml` → `confluence.log_book.*` (base URL, root page id)
  to resolve and re-fetch the log-book page.
- The candidate's run folder listing (to compare local file count against the
  log book's recorded attachment count).

## Writes
- **Deletes** `docs/agent/runs/{story_id}/` (the entire folder) for verified
  candidates only.
- **Updates** `docs/agent/run-status.md`: in the Closed runs table, replace the
  "Run folder" cell for a pruned story with a short pruned-notice + the
  Confluence log-book link (see Output format below). Never removes the table
  row itself — that row is the permanent lightweight ledger of what happened.
- **Appends** to `docs/agent/runs-pruned.md` (create if absent) — one line per
  pruned story: story id, prune date, local bytes freed, log-book URL. This is
  the durable record that survives even after the run folder is gone.

## Steps
1. **Collect candidates.** Read the Closed runs table in `run-status.md`. A row
   is a candidate only if:
   - Its outcome is `done`, `rejected`, or `failed` (i.e., it is actually in the
     Closed runs table — active-runs and awaiting-PO tables are never in scope).
   - Its story id matches the target project's real key pattern
     (`{jira.project_key}-\d+`, e.g. `DEMO-1234`) — **never** prune a
     documentation/example run (e.g. `DEMO-EXAMPLE`) or anything that doesn't
     match a real issue key. When in doubt, skip and flag rather than guess.
   - Its run folder still exists on disk (skip already-pruned rows silently).
2. **Verify-before-delete, per candidate:**
   a. Read `{story_id}-logbook.md`. If missing → **skip, flag** ("no log-book
      record — cannot verify externalization; leaving in place"). This is the
      single most important guard: no logbook record means no delete, ever.
   b. Re-fetch the Confluence page (`page id` from the logbook file) via the
      Confluence MCP. Confirm it is reachable (HTTP 200) and confirm its
      attachment list's count is >= the local run folder's file count (a proxy
      for "the full evidence set made it across"). If the MCP is unavailable,
      the page 404s, or the attachment count looks short → **skip, flag** with
      the specific reason. Never delete on an assumption that a past publish
      succeeded — re-verify live, every time.
   c. If both checks pass, the candidate is **verified**.
3. **Stage a preview.** Before deleting anything, print the full candidate list
   with columns: story id | local size | log-book link | verified (yes/reason
   if no). This mirrors the toolkit's staging habit even though it is not a
   Jira write — the operator should see what is about to be removed from the
   repo before it happens.
4. **Prune verified candidates:**
   - Delete `docs/agent/runs/{story_id}/` from the filesystem (run folders are
     gitignored per ADR-0005, so no `git rm` is needed; this skill does not
     itself run `git commit`).
   - Update the story's row in `run-status.md`'s Closed runs table: replace the
     "Run folder" cell with `_pruned {date} — see log-book_` linked to the
     Confluence URL.
   - Append the ledger line to `docs/agent/runs-pruned.md`.
5. **Report a summary:** N pruned (with bytes freed), M skipped (with reasons),
   and the ledger file location.

## Output format (ledger — `docs/agent/runs-pruned.md`)
```
| Story | Pruned date | Bytes freed | Log-book page |
|-------|--------------|-------------|----------------|
| DEMO-1234 | {YYYY-MM-DD} | 128K | https://confluence.example.invalid |
```

## Output quality rules
- Every pruned row's ledger entry and `run-status.md` cell links to a **specific**
  Confluence page id — never a bare "see Confluence" with no link.
- The preview step always runs before any deletion; the summary always states
  exactly what was skipped and why (never a silent partial run).

## Guardrails
- **Never delete an active run.** Only rows already in the **Closed runs** table
  are in scope — `awaiting_approval` and `awaiting_po` runs are untouched no
  matter how old.
- **Never delete without a verified, live-reachable log-book page.** A missing
  `{story_id}-logbook.md`, an unreachable page, an MCP failure, or a suspiciously
  low attachment count all mean **skip**, not "delete anyway."
- **Never prune example/template/non-matching ids** (e.g. `DEMO-EXAMPLE`).
- **Never delete `run-status.md` rows** — only the heavy per-run folder. The row
  (now pointing at the log-book link) is the permanent index entry.
- **Never touch Jira or edit a Confluence page** — this skill only reads
  Confluence to verify, and only deletes local files.
- This skill does not require the Jira approval gate (it is not a Jira write),
  but it does require an explicit operator invocation ("clean up closed runs")
  — it is never triggered automatically as a side effect of closing a run.
