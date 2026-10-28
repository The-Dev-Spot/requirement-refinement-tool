# Skill: skill-confluence-log

## Purpose
Publish run evidence to the Confluence **log book** — the single, bounded exception
to the "never edit a Confluence page" rule. Maintains a run-status **dashboard** on
the log-book root page and **one child page per story** carrying the curated run
evidence (Option A: high-value artifacts inline + all raw `.md` files attached).

> **Scope is hard-limited (L-0027).** This skill may create/update pages **only**
> under `confluence.log_book.root_page_id`. It never creates, edits, or deletes any
> other Confluence page (grounding/spec pages are strictly read-only). It never edits
> a Jira issue. Publishing to the log book is **evidence recording, not a Jira write**,
> so it does not consume the Jira approval gate — but it still obeys
> verify-before-write.

> **The log book is where story detail lives (rubric "Proportionality").** The
> Jira description is a lean payload (see `examples/lean-requirement.md`) whose first
> line links to this story page. Everything kept out of it — citations, quoted
> rules, precedent, risk mapping, proposal rationale, the original→new AC
> mapping — is in the rewrite's "Review notes" (rendered inline, verbatim) and
> the attached run docs. A Jira write must therefore never happen before this
> page exists; its URL is the `{logbook_url}` the payload links to.

## Reads
- **`.github/project-config.yaml`** → `confluence.log_book.*` (the single source of
  truth for the root page id, space key, title format, inline sections, and the
  attach-evidence flag) and `confluence.base_url`. Never hardcode these.
- `docs/agent/run-status.md` (the dashboard source).
- The target run folder `docs/agent/runs/{story_id}/`:
  - `{story_id}-run-summary.md`, `{story_id}-rewrite.md`,
    `{story_id}-proposed-comment.md` (rendered inline, in `inline_sections` order),
  - every other `{story_id}-*.md` (attached as evidence),
  - `{story_id}-logbook.md` if present (holds the existing Confluence page id).

## Writes
- **Confluence (log-book subtree only):**
  - The **root page** (`root_page_id`) — the run-status dashboard (update).
  - One **child page per story** titled per `story_page_title_format`
    (default `{story_id} - {summary}`) — create on first run, **update** thereafter.
  - **Attachments** on the story page: every `{story_id}-*.md` in the run folder.
- **Run folder:** `docs/agent/runs/{story_id}/{story_id}-logbook.md` — a small
  write-once/replace record mapping the story to its Confluence page id + URL +
  last-published timestamp (so re-runs update, never duplicate).
- Optional `{story_id}-decision-log.md` append recording the publish.

## Operations

### `publish_dashboard`
Render `run-status.md` onto the root page (`root_page_id`). Author in Markdown.
**Ordering (operator preference):** put **Active runs awaiting approval** first —
immediately under the page title and a one-line "maintained by the pipeline — do not
edit by hand" note — so the approval queue is the first thing the page shows. Then
**Closed runs**, then the **Story evidence pages** index (links to each child page),
then an **About / How to review** section carrying the run-status preamble and the
latest-run pointer. Do not prepend a table-of-contents macro (it would push the
active queue down). Update-in-place (the page already exists); never create a second
dashboard.

### `publish_story`
Create or update the story's child page and attach its evidence.
1. **Resolve the page** (idempotency): if `{story_id}-logbook.md` records a page id,
   use it; else search the root's children for a title starting with `{story_id}`.
   If found → **update**; if not → **create** under `root_page_id`.
2. **Compose the body deterministically — DO NOT hand-author or summarize it.**
   Run the builder, which reads the run folder and emits the page body with every
   `inline_sections` artifact included **verbatim**:
   ```bash
   python3 scripts/build-logbook-page.py {story_id}
   # writes docs/agent/runs/{story_id}/{story_id}-logbook-page.built.md and prints it
   ```
   Use that file's exact contents as the page body. It renders, in
   `inline_sections` order, the **full text** of `{story_id}-run-summary.md`,
   `{story_id}-rewrite.md`, and `{story_id}-proposed-comment.md`, plus the status
   panel and evidence list. If `python3` is unavailable, assemble the body **by
   hand from the template** (`docs/agent/templates/{story_id}-logbook-page.md`) — but
   still obey the verbatim rule below.

   > **VERBATIM RULE (L-0031 — non-negotiable).** The inline sections are a
   > **copy-paste of the whole source file**, not a précis. Never shorten, re-word,
   > bullet-ify, or replace them with a "see attached" pointer. The page must be the
   > full run evidence a reader can consume without opening the attachments. A page
   > whose inline sections are shorter than their source files is a FAILURE.
3. **Create/update** the page via MCP `confluence_create_page` /
   `confluence_update_page` (use the verified content format and `space_key` from config).
4. **Attach** every `{story_id}-*.md` (when `attach_evidence: true`) via
   the verified attachment capability of the authorized connector (or an authorized
   REST fallback when that capability is unavailable). On a re-run, an
   attachment that already exists must be **updated in place** (new version),
   not re-created — look up the attachment id by filename and POST to
   `/content/{id}/child/attachment/{attId}/data` (a plain POST to
   `/child/attachment` only creates *new* attachments and errors on existing
   names).

   > **Attachment verification (`L-0050`).** Tool success alone is not proof of an
   > upload. Re-read the page's attachment list and verify every expected filename
   > and version. If verification fails, record the failure; only use a REST
   > fallback after checking the configured service's API and available authority.
5. **Record** the page id + URL + timestamp in `{story_id}-logbook.md`.
6. **Self-check the published page (mandatory — L-0031).** Re-read the page you just
   wrote (`confluence_get_page`, `convert_to_markdown: true`) and verify **all** of:
   - the body length is **at least ~80%** of the combined length of the inline source
     files (`run-summary` + `rewrite` + `proposed-comment`); a body a fraction of that
     size means the inline content was summarized — **rebuild and update once more**;
   - each inline section is present — the first ~80 characters of each source file
     appear verbatim on the page;
   - the status panel, all inline sections, and the evidence list are all present.
   If any check fails, re-run the builder (step 2) and update the page again. Do not
   leave a truncated page published. Record the verified body length in
   `{story_id}-logbook.md`.

## Rendering rules (verify against the configured connector — L-0028)
- Author page bodies in **Markdown**: `##` headings, `|...|` tables, `-`/`*` bullets,
  and fenced code blocks (```` ```gherkin ````) all convert to Confluence storage.
- A **self-closing / simple-body macro** survives passthrough — use
  `<ac:structured-macro ac:name="toc"/>` for navigation.
- **Never put Markdown inside a macro `rich-text-body`** — the converter injects
  `<p>` tags and the storage XHTML fails to parse (`Unexpected close tag`). Keep long
  content (the rewrite) **visible**, not collapsed inside an Expand.
- Reuse/update the existing page. Do not assume delete privileges.

## Verify-before-write
- Re-read the target page before updating (confirm it is under `root_page_id` and the
  title matches the story) — never update a page outside the log-book subtree.
- On a re-run, update the existing story page and re-upload attachments as new
  versions; do not create a duplicate page.
- If `update` returns the server version error, the cause is almost always an invalid
  body (e.g. markdown inside a macro) — fix the body, do not blindly retry into a
  duplicate.

## Output quality rules
- The story page reads top-down: dashboard → story → evidence. The status panel names
  the verdict, mode, dates, Jira issue link, and exactly what was written to Jira.
- Inline sections are the reader's value; attachments are the audit trail. Both present.
- The dashboard mirrors `run-status.md` exactly — no divergent hand edits.

## Guardrails
- **Scope:** create/update only under `confluence.log_book.root_page_id`. Never touch
  any other Confluence page; never edit a grounding/spec page; never delete.
- No stage ownership — the orchestrator owns transitions and invokes this skill.
- No Jira writes here; this skill records evidence, it does not hand anything to the
  receiving team.
- Read all identifiers from `project-config.yaml`; never hardcode page ids or space keys.
