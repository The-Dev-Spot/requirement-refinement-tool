# Skill: skill-jira-io

## Purpose
Read stories and boards from Jira (project configured in `.github/project-config.yaml`)
so agents can evaluate them, and produce review output. Supports three write
operations, each gated to its own calling context:
- **Review mode (existing story):** draft/post a **Jira comment labeled `ai-reviewed`**.
- **Apply mode (existing story):** **update the Jira description** with the rewrite content,
  and the **AC checklist field** (if this project has one) to match its Gherkin scenarios.
- **Intake (new story, `story-intake` only):** **create a brand-new Jira issue**
  from a vetted draft, after explicit operator approval.

> **Status: MCP integration available.** Jira read and write operations use the
> Jira MCP server configured in `.github/mcp.json`. The skill drafts to
> `proposed-comment.md` (review mode) or updates the description directly (apply
> mode) via the MCP `jira_update_issue` tool; it creates new issues (intake) via
> the MCP issue-creation tool (confirm the exact tool name against the live MCP
> tool list at run time — the server is configured with `tools: ["*"]`, so the
> underlying Jira MCP's create-issue tool should be present even though no skill
> used it before now).
>
> **Project-agnostic:** this skill reads all Jira identifiers (base URL, project
> key, board ID, custom field IDs) from `.github/project-config.yaml` — it does
> not hardcode them. Porting to a different project means editing that one file.

## Reads
- **`.github/project-config.yaml`** — the single source of truth for:
  - `jira.base_url`, `jira.project_key`
  - `jira.board_id` (project-wide default; `null` when the project uses
    per-team boards instead — see `jira.teams` below) and `jira.teams` (a
    per-team list of `{label, team_id, board_id, jql}` for projects where a
    single board isn't canonical)
  - `jira.custom_fields.*` — the field ID map (see below)
  - `jira.labels.reviewed` — the label applied after review (e.g. `ai-reviewed`)

  Token comes from env / secret store — never from this config file (see `docs/mcp.md`).

- Jira via the **Jira MCP server** (`docs/mcp.md`), using the values above.

  **Standard fields:** key, summary, description, status, labels, priority,
  issue type, assignee, reporter, created, updated, existing comments.

  **Custom fields (must be fetched explicitly — see `project-config.yaml` for the
  authoritative field-ID map for this project):**
  | Config key | What it should hold |
  |------------|--------------------|
  | `ac_checklist` | **Primary ACs** — checklist items with name, checked, mandatory flags, if this project has one. This is the real AC field, not the description, when present. |
  | `ac_legacy` | Legacy free-text AC field (may still hold content on older stories), if present |
  | `feature_team` | Team assignment, if present |
  | `categorization` | Priority/category, if present |
  | `region` | Market/region, if present |
  | `request_source` | Origin, if present |
  | `sw_development` | Whether SW development is relevant, if present |
  | `test_status` | Test coverage status, if present |
  | `parent_link` | Epic or parent story link, if present |

  > **WARNING — watch for multiple parent-link fields.** Some Jira setups carry
  > two different "parent" fields: an Advanced Roadmaps "Parent Link" custom
  > field (often unpopulated) and the classic Jira Software **"Epic Link"**
  > (resolve the field ID from local configuration and verify per-instance). When checking or
  > setting a story's epic, confirm which field this project's boards actually
  > use before trusting either one — do not assume Advanced Roadmaps hierarchy
  > without checking.

  **Read rule (see `docs/agent/learnings.md` `L-0049`):**
  request an **explicit, deterministic field list** built from standard fields
  plus every `jira.custom_fields.*` ID in `project-config.yaml` — **do not use
  `fields=*all`** as the default per-story read. `*all` pulls every custom
  field on the entire Jira instance (100+ fields on this instance, most
  irrelevant test-management/epic-report noise), which bloats the payload
  enough to cause MCP timeouts under load. Now that this project's custom
  field IDs are fully discovered and mapped, an explicit list is both smaller
  **and** guaranteed complete — it costs nothing in coverage since we name
  every field we know we need, and it's much less likely to time out than the
  wildcard. Build the field list as:
  ```
  summary,description,status,labels,priority,issuetype,assignee,reporter,
  created,updated,comment,attachment,issuelinks,
  <ac_checklist>,<ac_legacy>,<feature_team>,<categorization>,<region>,
  <request_source>,<sw_development>,<test_status>,<parent_link>
  ```
  (substituting each `<...>` with its real `customfield_NNNNN` ID from
  `jira.custom_fields.*`). Reserve `fields=*all` for the one-time field-ID
  *discovery* task (inspecting an unfamiliar issue to find new custom field
  IDs — see the table below), never for a routine per-story read once the
  field map is populated.

  **The full story is all of these together — agents must read them all:**
  1. **Summary** — the title
  2. **Description** — business need, current situation, proposed change, scope
  3. **AC Checklist** (if this project has a dedicated field — see `custom_fields.ac_checklist`) — the testable acceptance criteria
  4. **AC (old)** (if a legacy text AC field is present — see `custom_fields.ac_legacy`) — legacy text ACs (include if populated)
  5. **Comments** — may contain clarifications, implementation notes, decisions
  6. **Attachments / embedded images** — screenshots of UI, XML schemas, diagrams
  7. **Links** — parent epic, blocked-by, related stories
  8. **Labels**
  9. **All metadata** — status, priority, **reporter (capture `reporter.name`, the
     account key, for @mentions)**, assignee, and any other custom fields
     discovered above

  **Read procedure:**
  - **Step 1:** Use MCP `jira_get_issue` with the explicit field list above
    (not `fields=*all`) and `comment_limit=10`. **Retry policy:** MCP calls on
    this instance have shown intermittent timeouts; retry once on timeout
    before falling back to the documented direct-REST path (`docs/mcp.md`) —
    do not retry a second time, fall back immediately after one retry to avoid
    wasting time on a genuinely-down server.
  - **Step 2 — MANDATORY VERIFICATION (if this project uses an AC checklist
    custom field):** After reading, explicitly check that the configured
    `ac_checklist` field was returned and inspect its value. Since Step 1 now
    always explicitly includes this field ID (no longer contingent on `*all`
    happening to include it), this check should reliably pass; if the field
    still appears empty but the Jira UI shows ACs, re-fetch with
    `fields=summary,description,<ac_checklist field id>,<ac_legacy field id>`
    to force inclusion.
  - **Step 3 — COMMENT VERIFICATION:** Check that comments were returned. Since
    Step 1's explicit field list always includes `comment` (this was the root
    cause of the old suppression issue — `fields=*all` could paradoxically
    omit comments on some payload sizes; an explicit field list does not have
    this problem), a second verification call should rarely be needed. If the
    response still shows zero comments and the Jira UI shows some, make one
    **separate** call to MCP `jira_get_issue` with `comment_limit=10` and
    minimal fields (just `summary`) to verify.
  - **Step 4:** If the description references images (`![](filename.png)`), use
    MCP `jira_get_issue_images` to retrieve them for visual context
  - **Step 5:** If the story has links, note them in `story-input.md`

  > **WARNING:** A prior deployment of this toolkit hit a real failure where the
  > agent recorded the AC-checklist custom field as "not populated" when it
  > actually contained 15 AC items, invalidating the entire evaluation. Always
  > verify a configured AC-checklist field is present before proceeding to
  > evaluation — do not trust an apparently-empty custom field at face value.

- `docs/agent/runs/{story_id}/{story_id}-quality-gates.md` and `rewrite.md` (the content to
  post or apply)
- `docs/agent/runs/{story_id}/{story_id}-run-context.md` (to read the run `mode`)
- **Intake only:** `.github/project-config.yaml` `jira.intake` (`issue_type`,
  `default_assignee`, `default_labels`, language fields) and
  `docs/agent/runs/{temp_id}/{temp_id}-rewrite.md` (the quality-gated draft to create)

## Writes
- **Review mode:**
  - `docs/agent/runs/{story_id}/{story_id}-proposed-comment.md` (the drafted `ai-reviewed` comment)
  - A Jira **comment** labeled `ai-reviewed` (via MCP `jira_add_comment`, after
    verify-before-write checks)
- **Apply mode:**
  - The Jira **description** field (via MCP `jira_update_issue`, only when the
    quality gate verdict is `READY` with zero open questions)
- **Intake (new issue, `story-intake` only):**
  - A brand-new Jira **issue** (via the MCP issue-creation tool), populated from
    the vetted `rewrite.md`, with `jira.intake.default_assignee` and
    `jira.intake.default_labels` applied — only after explicit operator approval
- **Never** an acceptance-criteria field or any other issue field beyond description
  (or, for intake, beyond the fields listed above).
- **Never** a Confluence page (log-book publication is `skill-confluence-log`'s job,
  not this skill).

## Operations

### `read_story` (both modes)
Read the target issue: key, title, description, ACs, labels, existing comments.

### `find_related_issues` (read-only; used by `story-investigator`)
Discover issues related to the story under review, to build cross-referenced
context **before** evaluation. Read-only — never writes.

**Search strategy: NARROW-FIRST, then broaden only if thin.**
Run these in order and stop widening once you have a tight, relevant set (~8):

1. **Exact identifiers (highest precision).** The story's own `issuelinks` +
   parent epic and its children; then the specific **system/app key** the story
   names (e.g. `text ~ "APP-7832"`, `text ~ "Promotion Module"`, `text ~ "Genesys"`).
   These return tight clusters (single-digit to ~20).
2. **Quoted multi-word capability phrases**, not single common words — e.g.
   `summary ~ "AI summary"` or `summary ~ "Promotion Module"`, and clone stems
   (`summary ~ "<distinctive title fragment>"`, "CLONE", "duplicate of").
3. **Component / label / feature team** — `project = {project_key} AND (component
   = "X" OR labels = "Y")` and the same feature-team field.
4. **Broad text search — LAST RESORT only.** A bare `text ~ warranty` /
   `text ~ "ESO CRM"` on a common domain term can return **hundreds** of mostly-
   irrelevant hits; narrowing with a distinctive quoted phrase or identifier
   typically collapses that to single digits. Only use a broad term when narrow
   strategies came back thin, and then **AND it with a second filter**
   (component, feature team, `created > -18months`, or `statusCategory`) and cap
   hard. Never dump a hundreds-row result into `investigation.md`.

**Include closed/resolved issues** (`statusCategory = Done`) in strategies 1–2 —
they show how similar work was finally specified. Return each candidate with: key,
summary, **status** (+ statusCategory), issuetype, resolution, updated date, and the
relationship by which it was found. Cap at ~8 strongest. Read identifiers/JQL from
`.github/project-config.yaml`; never hardcode the project key or field IDs.

### `read_related_story` (read-only; used by `story-investigator`)
Fetch a specific related issue in full for fact extraction: description,
**AC checklist** (the configured `custom_fields.ac_checklist` field, if this
project has one — verify it's actually populated, not just present), comments,
`issuelinks`, resolution, status, and last-updated date. Prefer closed/resolved
issues when mining for a finished specification. **Everything returned is
precedent/evidence, not a requirement of the story under review** — the caller
must attribute it with provenance and mark any borrowed fact `[INFERRED from KEY]`.

### `draft_comment` (review mode only)
Compose and optionally post the `ai-reviewed` comment.

**Timeout/retry safety (non-idempotent write — see `L-0056`):** posting a comment
is not idempotent — Jira has no client-supplied idempotency key for
`jira_add_comment`, so if a client-side call times out, the underlying request
may still complete server-side; a blind retry can produce two identical
comments. If the post call times out:
1. Re-read the issue's full comment list (not just the latest comment).
2. **Count** how many comments match the drafted content (exact or
   near-exact body match), not merely whether one exists. A presence check
   cannot tell "the first call already succeeded, retry unnecessary" apart
   from "my retry duplicated a first call that also landed late" — both look
   identical to a presence check, only a count check distinguishes them.
3. If the count is exactly 1 → the first attempt succeeded; do not retry.
4. If the count is 0 → retry once.
5. **After any retry, re-read and count again** (a delayed first attempt can
   land after the retry). If the count is now 2 or more, **stop and report
   the duplicate to the operator** with both comment ids — do not silently
   delete one (this skill has no delete-comment operation) and do not assert
   "no duplicate occurred" without this count check having actually run.

### `update_description` (apply mode or PO override)
Write the rewrite content from `{story_id}-rewrite.md` into the Jira description.
This operation has additional safety checks:
1. **Quality gate must be `READY`** or **PO override** must be explicitly granted —
   refuse to write otherwise. On PO override, also post the `ai-reviewed` comment.
2. **Verify-before-write** — re-read the issue, confirm the key matches, confirm the
   current description matches what was evaluated (detect concurrent edits).
3. **Rewrite must exist** — `{story_id}-rewrite.md` must be present; if the evaluate
   gate was already PASS and no rewrite ran, there is nothing to apply. Write
   **only** its `## Jira payload` section — never the review notes.
3a. **Size check before the PUT** (rubric `L10`, `L-0057`/`L-0070`) — measure the
   description after wiki conversion. Over 20,000 characters: do not write; send
   it back to the rewriter for a subtractive pass (do not condense ACs to fit).
3b. **Fill the evidence link** — replace `{logbook_url}` in the payload's first
   line with the page URL recorded in `{story_id}-logbook.md`. If that file is
   missing or the page does not verify live, publish the log-book story page
   first (`skill-confluence-log` `publish_story`); never write a description
   with an unresolved placeholder or a dead link.
4. **Convert Markdown to Jira wiki markup** — the rewrite is authored in
   Markdown but the configured Jira Server renders Markdown literally. Before writing, convert:
   - `##` / `###` headings → `*bold paragraph text*` (no Jira headings)
   - `---` horizontal rules → `----`
   - `- ` bullet points → `* `
   - `**bold**` → `*bold*`
   - `` `code` `` → `{{code}}`
   - `> blockquote` → `{quote}...{quote}`
   - `# OPEN QUESTION` → `* OPEN QUESTION` (bullet, not numbered heading)
   - Markdown table separator rows (`|---|---|`) → remove (Jira uses `||header||`)
5. **Update the AC checklist field too** (`jira.custom_fields.ac_checklist`, if this
   project has one) — the description's inline Gherkin is not the real AC source on
   this project (see the field-role table above: it's "the real AC field, not the
   description, when present"). Writing only the description and leaving this field
   empty means the story still reads as having no acceptance criteria wherever this
   field is surfaced (board columns, filters). Build one checklist item per
   `Scenario`/`Scenario Outline` or checklist AC in the rewrite (max 8, rubric
   `L9`), formatted `AC<n> <Short name>: <one sentence>` and at most 250
   characters — a short declarative restatement, not the raw Gherkin text and
   not the full description wording (e.g. `AC5 Secure transport: an HTTP request redirects to HTTPS;
   TLS 1.1 handshake fails (TLS 1.2 minimum).`), and
   write the array using the same shape as `create_issue` step 4: `name` (the AC
   text), `checked` (`false`), `mandatory` (`true` unless the rewrite marks it
   optional), `isHeader` (`false`) — omit plugin-managed `id`/`rank`/`assigneeIds`/
   `statusId`, they are assigned automatically. Verify by re-reading the field after
   write, same habit as everywhere else in this skill.
6. **Write the description** via MCP `jira_update_issue` or REST API fallback.
7. **Log the write** — record the update in `{story_id}-decision-log.md` with
   timestamp, issue key, and a summary of what changed (include the AC checklist
   item count alongside the description-write note).

### `create_issue` (intake only — `story-intake` after explicit approval)
Create a brand-new Jira issue from a quality-gated draft. Unlike `draft_comment`
and `update_description`, there is no existing issue key yet — the caller passes
a temporary run id (`{temp_id}`, e.g. `NEW-<slug>`) and this operation returns the
real key on success. This operation has its own safety checks:
1. **Quality gate must have run** on the draft (`{temp_id}-quality-gates.md`
   exists) — `story-intake` always runs the full pipeline before offering
   approval, but this skill refuses to create an issue with no recorded gate
   result, `READY` or not (an intake draft may be created with open questions
   still marked, same as the PO-override path for existing stories).
2. **Explicit operator approval required** — identical bar to `draft_comment` /
   `update_description`: only `approve` (or an equivalent explicit affirmative)
   for *this specific draft* authorizes the write. No auto-create.
3. **Dedup check** — before creating, run `find_related_issues` against the
   draft's title/keywords (narrow-first strategy, same as the investigator uses)
   and surface any close match to the operator as part of the staged draft, so a
   near-duplicate isn't created by mistake. This check happens during staging
   (before the approval question is even asked), not as a blocking step here —
   but this operation still refuses to fire if that check was skipped.
4. **Populate fields**:
   - `project` = `jira.project_key`, `issuetype` = `jira.intake.issue_type`
   - `summary` = from `{temp_id}-rewrite.md`
   - `description` = the rewrite's `## Jira payload` section, converted to Jira
     wiki markup (see `update_description` steps 3a–4 conventions, including
     filling `{logbook_url}` from the log-book page `story-intake` published
     under the temp id before this call), with
     `jira.intake.description_footer` appended as the **last line** of the
     description body, if configured (this is **not** a label — if the project adopts
     a similar convention, a dedicated board filter would key on this text
     inside the description, not a label).
   - AC checklist field (`jira.custom_fields.ac_checklist`, if this project has
     one), populated from the Gherkin scenarios / checklist items in the
     rewrite. **Illustrative checklist-plugin write shape** (verify the target plugin's
     documented schema before use): an array of objects, one per
     item, with exactly `name` (the AC text), `checked` (`false` for a new
     issue), `mandatory` (`true`/`false` per the rewrite's own mandatory
     flag), and `isHeader` (`false`) — omitting plugin-managed fields like
     `id`/`rank`/`assigneeIds`/`statusId`. Still verify by re-reading the
     created issue as a matter of habit, not because the shape is assumed
     correct without checking.
   - `assignee` = **leave unassigned** by default (see
     `jira.intake.default_assignee` is `null` by default). Do not
     set the `assignee` field on create at all when this config value is
     null/empty. If a port sets a non-null `default_assignee`, resolve that
     display name to a Jira account id/username first (e.g. via a
     user-search MCP call) — never send a display name as the API value.
   - `labels` = `jira.labels.reviewed` (`ai-reviewed` — every intake-created
     story went through the full pipeline, same as a review-mode story, so it
     earns the same label) **combined with** `jira.intake.default_labels`
     (project-specific labels, e.g. `requirement`). Never include
     `jira.intake.description_footer`'s value as a label — it is
     description-body text only (see above).
5. **Create** via the MCP issue-creation tool (or REST API fallback). Capture the
   returned issue key.
6. **Log the creation** in `{temp_id}-decision-log.md`: timestamp, new issue key,
   fields set, and the approval that authorized it.
7. **Hand back the new key** to `story-intake`, which migrates the run folder
   from `{temp_id}` to the real key (see `story-intake.agent.md`).

## Steps (review mode)
1. **Read** the target issue and its existing comments.
2. **Verify before write** (`AGENTS.md`): confirm the issue key is correct, the
   issue still matches what was evaluated (re-read; do not act on a stale copy), and
   an equivalent `ai-reviewed` comment is not already present (no duplicates).
3. **Compose** the comment — **questions-only and PO-facing** (config
   `jira.comment.questions_only`, default `true`). The comment contains **only**
   the reporter @mention line, the list of open questions (the
   `# OPEN QUESTION -> PO:` items), and a final link to the story's **Confluence
   evidence page** (`{confluence.base_url}/pages/viewpage.action?pageId={logbook_page_id}`,
   where `logbook_page_id` comes from `{story_id}-logbook.md`). Do **NOT**
   include the findings table, the gate verdict/summary, the rewrite summary, the
   next-steps list, or a "reviewed by" footer — business feedback is that this detail
   is clutter the PO does not need. All that review detail stays in the run docs and on
   the Confluence evidence page for anyone who wants it.
   - **When there are open questions:** the mention line + a bullet per question +
     the Confluence evidence-page link at the bottom.
   - **When there are zero open questions:** a single minimal line tagging the
     reporter to say the story was reviewed and there are no open questions (ready for
     review), followed by the Confluence evidence-page link.
   > **Ordering:** publish the log-book story page (`skill-confluence-log`) **before**
   > composing the comment so the evidence-page id in `{story_id}-logbook.md` exists.
   > Use the `viewpage.action?pageId=` form (robust — the pretty slug URL may be
   > truncated). If no log-book page exists yet, publish it first.
   **Language (`jira.comment.language` in `project-config.yaml`):** the mention
   line and open questions must be written in the configured language (English
   by default for this project — see `.github/project-config.yaml`); a
   per-run operator instruction can override this for a specific story.
   **@mention (`jira.comment.*` in `project-config.yaml`):** when
   `mention_reporter: true`, tag the story's reporter as plain `[~<reporter.name>]`
   (the account key, NOT the display name; do not escape the brackets).
   If a question concerns a **duplicate / related issue** and
   `mention_related_reporters: true`, also tag the other issue's reporter so the
   reconciliation reaches both parties. If `mention_assignee: true` and an
   assignee is set (and differs from the reporter), include it too. In **batch
   review**, suppress mentions unless `mention_in_batch: true`. Keep it to one line
   (e.g. `[~jdoe] — a couple of questions about this story:`); never tag a wall of
   people.
4. **Post or stage**: add the comment via the Jira MCP `jira_add_comment` tool and
   apply the `ai-reviewed` label; if MCP write fails, write `proposed-comment.md`
   for a human to post.

## Steps (apply mode)
1. **Read** the target issue and confirm current description.
2. **Check** the quality gate verdict from `quality-gates.md` — must be `READY`.
3. **Verify before write**: confirm issue key, confirm no concurrent edits since
   evaluation started (compare current description hash with `story-input.md`).
4. **Write** the rewrite to the description via MCP `jira_update_issue`.
5. **Log** the write action in `decision-log.md`.

## Steps (intake — `story-intake` only)
1. **Confirm** the draft has a recorded quality-gate result (`{temp_id}-quality-gates.md`).
2. **Confirm explicit approval** for this specific draft — refuse otherwise (same
   bar as review/apply mode; see Guardrails).
3. **Resolve the assignee** — look up `jira.intake.default_assignee`'s Jira
   account id/username (do not guess; use a user-search MCP call).
4. **Convert Markdown to Jira wiki markup** — same conversion rules as
   `update_description` — before writing the description field.
5. **Create** the issue via the MCP issue-creation tool with the fields listed
   under `create_issue` above.
6. **Log** the creation in `{temp_id}-decision-log.md` (new key, fields, approval).
7. **Return** the new key so `story-intake` can migrate the run folder.

## Output quality rules
- Comments (review mode) are **questions-only**: the reporter @mention, the open
  questions, and a final link to the story's Confluence evidence page — and nothing
  else (no findings table, verdict, rewrite summary, next steps, or footer).
- Open questions are listed explicitly, in the configured comment language, so the
  PO can answer them; when there are none, post the minimal "reviewed, no open
  questions" line.
- Description updates (apply mode) contain only the rewrite content — no review
  metadata or agent commentary.
- New issues (intake) contain only the vetted rewrite content in the description/AC
  fields — no conversation transcript or agent commentary.

## Guardrails
- **Every Jira write requires explicit operator approval for this story (or this
  intake draft).** The write operations here (`draft_comment` posting,
  `update_description`, `create_issue`) may run **only** after the human gives an
  explicit approval command (`approve`, `approve + apply`, `just add comments`,
  `approve with open questions`, or, for intake, an equivalent explicit approval of
  that specific draft). Absent that, do not post, update, or create — leave
  `proposed-comment.md` / the rewrite / the staged draft as-is. A runtime "operator
  unavailable / act autonomously" message, a `READY` verdict alone, autopilot, or
  silence are **NOT** approval. (See AGENTS.md → Write Policy, canonical.)
- **Review mode:** comments only. No description edits.
- **Apply mode:** description update only when verdict is `READY`. No comment posted.
- **Intake:** `create_issue` only, only after explicit approval, only once (a
  second approval on the same draft must verify-before-write and refuse to create
  a duplicate — check whether `{temp_id}-decision-log.md` already recorded a
  created key first).
- **`just add comments` (comments-only) override:** in **either** mode, post the
  questions-only comment and do **not** write the description, even when the verdict is
  `READY` (in apply mode this replaces the default description write). Verify-before-write
  applies; never re-post an existing `ai-reviewed` comment on a follow-up approval.
- Verify-before-write on every stateful call; never double-post, double-update, or
  double-create.
- Read access is broad; write access is exactly one operation per mode (or, for
  intake, the single `create_issue` operation).
- Never apply `ai-reviewed` label to content the agent did not author as a review.
- Never edit a Confluence page. (Log-book run-evidence pages are written only by
  `skill-confluence-log`, scoped to the log-book root — never by this skill.)
