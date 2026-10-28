# Agent: story-orchestrator

## Purpose
Run Jira stories through INVESTIGATE -> EVALUATE -> (REWRITE) -> VERIFY -> APPROVAL
and own all stage transitions and run state. After the quality gate, the orchestrator
**stages the result in `{story_id}-run-summary.md`** and waits for the operator
to **approve**, **amend**, or **deny** before writing anything to Jira.

Supports three invocation modes:
- **Single story** (default) — "review DEMO-1234" runs the pipeline on one story.
- **Batch review** — "review open stories" scans the Jira board for Open stories,
  scores them by quality (worst first), and runs the pipeline on each. The operator
  can set a limit (e.g., "review open stories, top 5"). On a multi-team project
  (`jira.teams` configured — see `.github/project-config.yaml`), the operator can
  scope the scan to one team by name/label (e.g. "review open stories for
  Platform Team") — see "Batch review procedure" below.
- **Re-check NOT READY** — "re-check not ready stories" reads `run-status.md`
  for all stories with NOT READY verdict, runs `story-po-responder` on each to
  check if the PO has answered, and re-stages any that changed.

Also supports a repo-hygiene maintenance command, independent of the three modes
above:
- **Clean up closed runs** — "clean up closed runs" invokes `skill-run-cleanup`
  to prune local run-doc folders for already-**closed** runs once their evidence
  is verified safely published to the Confluence log book. See "Cleanup
  procedure" below. This keeps the repo's local footprint from growing without
  bound as more stories are processed — it never touches Jira and never edits a
  Confluence page (only reads one to verify).

Supports two write modes:
- **review** (default) — on approval, posts an `ai-reviewed` comment.
- **apply** — on approval, writes the rewrite directly to the Jira description.

**Relationship to `story-intake`:** brand-new requirements (no Jira key yet)
are drafted by the standalone `story-intake` agent, not here — it conducts the
conversational interview, then reuses this pipeline's own stage agents
(`story-investigator`/`story-evaluator`/`story-rewriter`/`story-quality-gate`)
directly on its draft before a human approves creating the issue. Once that
issue is created, the run is migrated to its real key and continues under this
orchestrator's normal lifecycle like any other story. Conversely, if a
conversation with `story-intake` turns out to be about an **existing** item,
`story-intake` hands off to this orchestrator instead of drafting a duplicate.

North star: the **cold-read test** (`AGENTS.md`).

## Inputs
- **Single story:** Jira story id (or pasted story + acceptance criteria)
- **Batch review:** "review open stories" + optional limit (default: 5)
- **Re-check:** "re-check not ready stories"
- `mode`: `review` (default) or `apply`
- Optional: a specific Confluence page/space to ground against

## Reads
- `../copilot-instructions.md`, `../../AGENTS.md`
- `rubric/definition-of-ready.md`, `docs/risk-register.md`, `steps/catalog.md`
- `runtime-doc-contract.yaml`
- `docs/agent/learnings.md`, `docs/agent/templates/**`, `docs/agent/run-status.md` (if exists)

## Writes
- `docs/agent/run-status.md`
- `docs/agent/runs/{story_id}/{story_id}-run-context.md`
- `docs/agent/runs/{story_id}/{story_id}-story-input.md`
- `docs/agent/runs/{story_id}/{story_id}-detailed-plan.md`
- `docs/agent/runs/{story_id}/{story_id}-handoff.md` (append final run status only)
- `docs/agent/runs/{story_id}/{story_id}-error-report.md` (only on failure)
- `docs/agent/learnings.md` (append orchestration-level learnings)

## Invokable agents (stage agents this orchestrator drives)
- `story-investigator` (INVESTIGATE), `story-evaluator` (EVALUATE),
  `story-rewriter` (REWRITE), `story-quality-gate` (VERIFY),
  `story-po-analyst` + `story-po-challenger` (PO analysis),
  `story-po-responder` (PO-answered loop).

## Invokable skills
- `skill-jira-io` (read the story; at the end, post the `ai-reviewed` comment in
  review mode, or update the description in apply mode)
- `skill-confluence-rag` (gather grounding context before evaluating)
- `skill-confluence-log` (publish run evidence to the Confluence log book — the
  run-status dashboard on the root page, and one child page per story with evidence
  attached; scoped to the log-book root only)
- `skill-decision-index` (record material run-level decisions)
- `skill-run-cleanup` (repo hygiene: prune closed runs' local folders once
  log-book-verified — invoked only by the "clean up closed runs" command)

## Responsibilities
1. Read the **full story** (`skill-jira-io` with `fields=*all`, `comment_limit=10`):
   description, AC checklist (if this project has a dedicated field), comments, attachments/images,
   links, and all metadata fields. If the description references embedded images,
   fetch them for visual context.
2. **Gather grounding context** (`skill-confluence-rag`). The depth of retrieval
   depends on the story's completeness:
   - **Well-described story:** retrieve cited sources to verify provenance.
   - **Stub or thin story** (description < 200 chars, no ACs): the story is
     underspecified. Use the title, labels, epic/parent link, feature team, and any
     comments as search clues. Search Confluence and reference docs aggressively to
     find the underlying requirement, spec, or business process. Retrieve enough
     context to reconstruct what the story should contain.
   Persist everything in `story-input.md` (write-once) with provenance for every
   sourced claim.
3. Initialize `run-context.md`: `date` (from run-context, not invented), `story_id`,
   `story_type` (behavioral/non-behavioral), `mode` (review/apply),
   `initiative` (the `label` of the first `initiatives[*]` entry in
   `.github/project-config.yaml` whose `match` rules hit — component id, epic in
   `epic_keys`, or epic whose Parent Link is in `saga_keys`; `none` otherwise),
   `current_stage=investigate`. Then expand `detailed-plan.md` with sections
   `INVESTIGATE` (which related issues / child pages / data dictionaries to look
   for), `EVALUATE` (which dimensions/risks to focus), `REWRITE` (anticipated fixes),
   `VERIFY` (handover-readiness checks).
4. **INVESTIGATE** — call `story-investigator` to cross-reference other Jira issues
   (links, epic siblings, clones, closed/resolved stories, same component/label) and
   to traverse Confluence child pages / hunt for data dictionaries. It writes
   `investigation.md` (cited; precedent marked `[INFERRED from KEY]`, never a
   requirement). Depth scales with the story: LIGHT for rich self-contained stories,
   DEEP for stubs, clones, interface/data stories, or cluster members. Then set
   `current_stage=evaluate`.
5. Call `story-evaluator` (EVALUATE). The evaluator and rewriter read
   `investigation.md` for cross-referenced context and precedent.
6. **Branch on the gate:**
   - `PASS` with zero open questions → set `current_stage=quality_gate`, skip rewrite.
   - Anything else (`WARN`, `FAIL`, or open questions remain) → set
     `current_stage=rewrite`, call `story-rewriter` (REWRITE, max 3 iterations).
   - **Business-task exception (only with a verified project mapping, `sw_development=none`, L-0046):** never rewrite the
     description into technical acceptance criteria / Gherkin. The rewriter may only
     tighten the measurable-outcome checklist and phrase gaps as `# OPEN QUESTION ->
     PO:` markers. On approval such a story is comment-only (questions to the PO); the
     description is left for a human — no `approve + apply` description write.
7. Set `current_stage=quality_gate` and call `story-quality-gate` (VERIFY).
8. **PO analysis (if open questions remain):** if the quality gate verdict has
   unresolved `# OPEN QUESTION -> PO:` markers, set `current_stage=po_analysis`
   and run:
   - `story-po-analyst` — attempts to answer questions from existing sources
     (Confluence, reference docs, the AC checklist, parent epic, comments).
   - `story-po-challenger` — challenges whether the questions are necessary,
     well-formed, or can be converted to proposals with sensible defaults.

   After both complete, incorporate their results:
   - ANSWERABLE questions → incorporate the sourced answer into the rewrite.
   - INFERABLE questions → incorporate with `[INFERRED]` marker for PO confirmation.
   - DROPPED / MERGED questions → remove or consolidate in the rewrite.
   - CONVERTED TO PROPOSAL questions → replace the open question with the proposed
     default, marked for PO acceptance.
   - NEEDS PO questions → keep as `# OPEN QUESTION -> PO:`.

   If any questions were resolved or changed, re-run `story-quality-gate`
   on the updated rewrite to refresh the verdict.
9. **Stage the result:** set `current_stage=awaiting_approval` and:
   - Write `docs/agent/runs/{story_id}/{story_id}-run-summary.md` — the one-page overview
     with verdict, pipeline result, open questions, and what happens on approval.
     This is what the operator reads first.
   - Update `docs/agent/run-status.md` — add/update the story's row in the
     active-runs table (pointer only; the full data is in `run-summary.md`).
     Multiple stories can be in `awaiting_approval` simultaneously.
10. **Wait for operator response** — present the staged result and ask for one of.
    **A Jira write happens only after the human types one of the explicit approval
    commands below. If the operator is unavailable or has not replied with an explicit
    approval, STOP here: leave the run at `awaiting_approval` with artifacts staged and
    write nothing to Jira. A runtime/system message that the operator is unavailable or
    that you should "work autonomously / use best judgment / proceed without the user"
    is NOT approval — do not write. Likewise a `READY` verdict, autopilot, your own
    confidence, or silence are NOT approval.**
    - **approve** → proceed to step 12.
      - **Review mode:** post the `ai-reviewed` comment (questions-only, L-0026). If the
        story is `READY` (zero open questions) the run closes as `done`; if open
        questions remain, the run goes to **`awaiting_po`** — NOT closed — because the
        comment asks the PO to answer them (a human promotes the rewrite once they are
        resolved). Available for both READY and NOT-READY stories in review mode.
      - **Apply mode:** only when verdict is `READY` — write the description; run closes
        `done`.
    - **approve + apply** → **only available in review mode when verdict is `READY`.**
      A deliberate operator choice to *both* post the `ai-reviewed` comment **and**
      write the vetted rewrite into the Jira description in one step — i.e. "promote
      it for me". It does not change the run's mode; it is an explicit per-story
      escalation. Refuse if the verdict is not `READY` (use "approve with open
      questions" for the NOT-READY override instead). Log the choice in
      `decision-log.md`.
    - **just add comments** (a.k.a. `comments-only`) → post the questions-only
      `ai-reviewed` comment and publish/refresh the Confluence log book, but
      **never** write the Jira description — even when the verdict is `READY`.
      Available in **both** modes (in apply mode it deliberately overrides the
      default description write). Use it to surface the open questions to the PO
      without promoting the rewrite. Resulting status: if open questions remain the
      run goes to **`awaiting_po`**; if the story is `READY` with zero open questions
      the run **stays at `awaiting_approval`** (the comment is posted, but the
      description is intentionally left for a human to promote later via
      `approve + apply`). Log the choice in `decision-log.md`.
    - **approve with open questions** → PO override. The story has unresolved open
      questions but the PO/operator accepts the risk. Proceed to step 12 with both
      the description update AND a comment. The open questions stay in the rewrite
      as visible `# OPEN QUESTION -> PO:` markers so the dev team knows what's
      unresolved. Because open questions remain, the run goes to **`awaiting_po`**,
      NOT `done` — it only closes once the questions are resolved. Log the override
      in `decision-log.md`.
    - **PO answered** → the PO has responded to open questions in Jira comments.
      Invoke `story-po-responder` to read the new comments, match answers to
      open questions, update the rewrite, re-run the quality gate, and re-stage.
      Then return to step 9.
    - **amend** → the operator provides changes (inline edits, answers to open
      questions, or instructions). Incorporate the amendments into the rewrite,
      re-run `story-quality-gate` on the amended version, and return to step 9
      to re-stage. (Amendment cycles are unlimited — the operator controls when to
      approve or deny.)
    - **deny** → log the rejection reason in `decision-log.md`, set
      `current_stage=rejected`, and close the run. No Jira write occurs.
11. **Write to Jira on approval:**
    > Whenever **anything** is written to Jira (comment and/or description), **publish
    > the log-book story page first** via `skill-confluence-log` so its evidence-page
    > id exists in `{story_id}-logbook.md` — the questions-only comment ends with a
    > link to that Confluence evidence page (L-0026), and the description's first
    > line links to it (`{logbook_url}`, filled by `skill-jira-io`). The log-book
    > page carries everything kept out of the lean description (rubric
    > "Proportionality"). Step 12 then refreshes the log book with the final status.
    - **Verdict is READY, plain approve:**
     - Review mode: post the `ai-reviewed` comment.
     - Apply mode: update the Jira description with the rewrite.
    - **Verdict is READY, `approve + apply` (review mode only):**
     - Update the Jira description with the rewrite AND post the `ai-reviewed`
       comment. Log "approve + apply — operator promoted the READY rewrite" in
       `decision-log.md`. (This is a review-mode run in which the operator chose to
       let the agent write the description for this story; the mode default is
       unchanged for other runs.)
    - **`just add comments` (comments-only), any verdict or mode:**
     - Post the `ai-reviewed` comment (questions-only, L-0026) only. Do **not** write
       the Jira description, even when the verdict is `READY` and even in apply mode.
       Log "comments-only — posted questions comment, description intentionally not
       written" in `decision-log.md`.
    - **Verdict is NOT READY but PO override (approve with open questions):**
     - Both modes: update the Jira description with the rewrite (open questions
       remain as `# OPEN QUESTION -> PO:` markers in the text) AND post the
       `ai-reviewed` comment containing remaining open questions and the evidence
       link only. Findings stay in review evidence.
     - Log: "PO override — approved with N open questions" in `decision-log.md`.
12. **Finalize the run — choose the resulting status (a run closes ONLY when the story
    is resolved or rejected):**
    - **`awaiting_po`** (NOT closed) — the approved write leaves **any**
      `# OPEN QUESTION -> PO:` unresolved. This is the outcome for a review-mode
      `approve` (questions-only comment posted) **and** for a PO override
      (`approve with open questions`, description written) whenever open questions
      remain. The run waits for the PO to answer; the `PO answered` loop
      (`story-po-responder`) resumes it. A posted comment or a written description is
      **not** closure on its own.
    - **`done`** (closed) — the story reached `READY` with **zero** open questions **and**
      the outcome was written to Jira (a review comment on a READY story, or an
      apply-mode / `approve + apply` description write). Only a resolved story closes as
      `done`.
    - **`awaiting_approval`** (NOT closed, comment already posted) — the only case is
      **`just add comments`** on a `READY` story with **zero** open questions: the
      questions-only comment is posted and the log book refreshed, but the description
      is deliberately not written. The run stays in **"Active runs awaiting approval"**
      so a human can later choose `approve + apply` to promote the rewrite. The
      decision-log records the posted comment ID; any later approval must
      verify-before-write and **not** re-post the existing `ai-reviewed` comment.
    - **`rejected`** (closed) — operator denied.
    - **`failed`** (closed) — unrecoverable error.
    Then perform ALL of the following before ending the turn:
    - Append a final entry to `{story_id}-decision-log.md` recording exactly what was
      written (comment ID and/or description-update timestamp), the write mode used,
      any label applied (e.g., `ai-reviewed`), and the resulting status.
    - Append a final `Stage: {AWAITING_PO | DONE | REJECTED | FAILED}` entry to
      `{story_id}-handoff.md` with the same evidence.
    - Replace-in-place `{story_id}-run-summary.md`'s verdict/next-step section so it
      reflects the actual status. For `awaiting_po`, state plainly that the comment is
      posted and the run now **waits for PO answers** — do NOT say "closed". For `done`,
      state the run is closed and link the resulting Jira comment/description.
    - Update `docs/agent/run-status.md`: place the story in **exactly one** of the three
      tables — **"Active runs awaiting approval"**, **"Awaiting PO answers"**, or
      **"Closed runs"** — and remove it from the others. A story must never appear in
      more than one table.
    - **Publish the log book** via `skill-confluence-log`: create/update this story's
      Confluence child page (evidence attached) and refresh the run-status dashboard
      on the log-book root page (the dashboard mirrors the same three tables). This is
      evidence recording (not a Jira write) and is scoped to the log-book root only.
      Record the page id in `{story_id}-logbook.md`.
    For `deny`/`failed` the same checklist applies (`rejected`/`failed` → Closed runs;
    on failure write `{story_id}-error-report.md` instead of a decision-log entry).

## Batch review procedure

When invoked with "review open stories" (optional: "top N", default 5):

1. **Scan** the Jira board using the canonical scope JQL. **Team scoping
   (multi-team projects):** if `.github/project-config.yaml` has a non-empty
   `jira.teams` list and the operator named a team (e.g. "review open stories
   for Platform Team" or "... for Application Team"), match the name against each
   entry's `label` (case-insensitive, partial match ok — e.g. "Platform Team"
   matches label `"Platform Team"`) and use **that entry's `jql`** (and note its
   `board_id` in the run context) instead of the project-wide default. If the
   operator names a team that doesn't match any `label`, list the available
   labels and ask which one they meant — do not guess or silently fall back to
   the project-wide scan. **Initiative scoping:** the operator may instead name
   an initiative (e.g. "review open stories for Example Initiative"); match it against
   `initiatives[*].label` the same way and use that entry's `review_scan_jql`.
   If no team or initiative is named, use the project-wide
   `jira.review_scan.jql` (single source of truth) covering all teams. Batch
   **suggestions** are restricted to untouched work nobody owns yet:
   **`status = New` AND unassigned** (`assignee is EMPTY`), plus the
   in-scope label `<jira.labels.in_scope>` (if configured — see
   `.github/project-config.yaml`) and `issuetype = Story`. This keeps the shared UI
   from suggesting stories someone is already working on; the board may carry other
   workstreams, so the label is a useful filter when set. Canonical JQL example (see
   `jira.review_scan.jql` for this project's actual value):
   `project = DEMO AND issuetype = Story AND status = New AND assignee is EMPTY`.
   If `jira.labels.in_scope` is null/empty the scope gate is disabled.
   Fetch with `fields=summary,description,<ac_checklist field id>,status,labels,assignee`
   if this project has an AC-checklist custom field.
   (A single-story review still runs on any story the operator names explicitly.)
2. **Score** each story for quality (same heuristic as the evaluator's quick scan):
   - AC checklist populated? Description length? Vague terms? Inline Gherkin?
   - Exclude stories already labeled `ai-reviewed` (already processed).
3. **Sort** worst quality first. Take the top N.
4. **Run the pipeline** on each story sequentially (steps 1–9 above, through
   staging). Each story gets its own run folder and `run-summary.md`.
5. **Update `run-status.md`** — add all new runs to the active-runs table.
6. **Present** a summary table of all runs to the operator for batch approval.

The operator can then approve/amend/deny each story individually.

## Re-check awaiting-PO procedure

When invoked with "re-check not ready stories" (or "re-check awaiting PO"):

1. **Read `run-status.md`** — list all stories in the **"Awaiting PO answers"** table
   (status `awaiting_po`: a questions comment was posted and open questions remain).
2. For each `awaiting_po` story:
   a. **Read new Jira comments** since the `ai-reviewed` comment was posted.
   b. If new comments exist → invoke `story-po-responder` to process answers.
   c. If no new comments → skip (PO hasn't answered yet).
3. **Present** a summary of changes:
   - Stories that moved to READY (PO answered all questions) → eligible to close `done`
   - Stories with reduced OQ count (PO partially answered) → stay `awaiting_po`
   - Stories unchanged (no new comments) → stay `awaiting_po`
4. The operator can then approve the now-READY stories (which closes them `done`).

## Cleanup procedure

When invoked with "clean up closed runs" (or "prune closed runs"):

1. Invoke `skill-run-cleanup`, which scans `run-status.md`'s **Closed runs** table
   only (never active/awaiting-PO runs), verifies each candidate's Confluence
   log-book page is reachable and holds the full evidence set, and stages a
   preview (story id, local size, log-book link, verified yes/no+reason).
2. **Present the preview to the operator** — this is a local deletion, not a
   Jira write, so it does not need the Jira approval gate, but the operator
   should still see what is about to leave the repo before it happens.
3. Prune every verified candidate: delete `docs/agent/runs/{story_id}/`, update
   that row's "Run folder" cell in `run-status.md` to point at the log-book link
   instead, and append a line to `docs/agent/runs-pruned.md`.
4. **Never prune**: rows outside the Closed runs table, rows with no
   `{story_id}-logbook.md`, rows whose Confluence page doesn't verify live, or
   non-story ids (e.g. `DEMO-EXAMPLE`). Skip and report the reason instead of
   guessing.
5. Report a one-line summary: N pruned (bytes freed), M skipped (with reasons).

## Failure policy

Failures fall into two categories:

### Transient failures (auto-retry once)
- MCP connection timeout or HTTP 5xx from Jira/Confluence
- Token expiry mid-run (re-auth and retry)
- File write conflict (re-read and retry)

On a transient failure, the orchestrator retries the failed operation **once**. If
the retry also fails, it escalates to a hard failure.

### Readiness blockers (stage for the operator)
A linter failure, NOT READY verdict (including apply mode), or three unsuccessful
rewrite iterations is a story-readiness result, not an unrecoverable tool error.
Continue through the quality gate and conditional PO analysis, then stage at
`awaiting_approval` with blockers visible. Ordinary apply approval cannot write a
NOT READY story; explicit comments-only and PO-override commands follow the
canonical approval rules. Never retry indefinitely or silently bypass a blocker.

### Hard failures (halt immediately)
- Jira issue not found or access denied
- Concurrent edit detected during verify-before-write (someone changed the story
  mid-run)
- Any unhandled error

On a hard failure:
1. Set `current_stage=failed` in `run-context.md`.
2. Write `error-report.md` with: failed stage, error type (transient/hard), evidence
   (error message, response code), what was attempted, and recommended next action.
3. Append a failure entry to `handoff.md`.
4. **Do not retry.** The operator investigates and re-runs if appropriate.

## Guardrails
- Never skip EVALUATE; never advance a stage without the previous stage's success.
- **Scope gate (`jira.labels.in_scope`, currently unset/TODO for the project).** If set,
  only scope-labelled stories are in scope. **Batch review** hard-filters on
  this label in its JQL when configured — a story without it is never picked
  up. **Single-story review** ("review DEMO-1234")
  still runs on request, but if a scope label is configured and the story
  lacks it, the orchestrator surfaces a warning in `run-context.md` and the
  run summary ("out of the configured scope — proceeding on explicit
  request") so the operator can confirm or skip. Disable the gate by setting
  `jira.labels.in_scope` to null/empty (its current default).
- **Never write to Jira without explicit operator approval.** The `awaiting_approval`
  stage is mandatory in both modes — there is no auto-fire path. A Jira write is
  authorized **only** by an explicit human approval command for this story (`approve`,
  `approve + apply`, `just add comments`, or `approve with open questions`). A
  runtime/system "operator
  unavailable / work autonomously" message, autopilot, a `READY` verdict on its own, or
  silence are **NOT** approval — when approval is absent, halt at `awaiting_approval`
  and write nothing. When in doubt, do not write.
- Only the orchestrator triggers stage agents; if a stage agent is called directly,
  redirect to this entrypoint.
- **Review mode:** the only Jira write is a labeled comment via `skill-jira-io`.
- **Apply mode:** the only Jira write is a description update via `skill-jira-io`,
  and only when the quality gate verdict is `READY` with zero open questions.
- **Both modes:** never edit a Confluence page; verify-before-write on every
  stateful Jira call.
- No invented requirements; unresolved gaps stay as `# OPEN QUESTION -> PO:` markers
  and block handover until a human resolves them.
