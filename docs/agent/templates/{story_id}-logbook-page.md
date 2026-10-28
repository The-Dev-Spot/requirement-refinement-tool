# Log-book Story Page Template — {story_id}

> Authored by `skill-confluence-log`. This is the **Confluence** story page under the
> log-book root (`confluence.log_book.root_page_id`). Published in **Markdown**
> (`content_format: markdown`). One page per story; updated in place on re-runs.
>
> **Title:** `{story_id} - {summary}` (per `confluence.log_book.story_page_title_format`).
>
> **Rendering (L-0028):** headings / tables / bullets / fenced code convert cleanly.
> Use the `toc` macro for navigation. Do NOT wrap Markdown in a macro body. Keep the
> rewrite visible (not collapsed). Attach every `{story_id}-*.md` as evidence.

<ac:structured-macro ac:name="toc"/>

## {story_id} — {summary}

> Run evidence log — maintained by the story pipeline. The Jira issue itself is the
> source of truth; this page records what the review run produced. Do not edit by hand.

| | |
|---|---|
| **Jira** | [{story_id}]({jira_base_url}/browse/{story_id}) |
| **Verdict** | {READY | NOT READY} — {one-line reason} |
| **Mode** | {review | apply} |
| **Type** | {behavioral | non-behavioral} |
| **Reporter** | {reporter display name} |
| **Run status** | {awaiting_approval | done | rejected | failed} |
| **Written to Jira** | {comment id / description-updated timestamp / none} |
| **Opened / Closed** | {start date} / {closed date or —} |
| **Open questions** | {count} |
| **Run folder** | `docs/agent/runs/{story_id}/` |

---

## Run summary
<!-- inline (VERBATIM, L-0031): paste the ENTIRE contents of {story_id}-run-summary.md here. Do NOT summarize. -->
{paste the full, unabridged contents of {story_id}-run-summary.md}

---

## Proposed / posted comment
<!-- inline (VERBATIM, L-0031): paste the ENTIRE contents of {story_id}-proposed-comment.md here. Do NOT summarize. -->
{paste the full, unabridged contents of {story_id}-proposed-comment.md — questions-only, per L-0026}

---

## Rewrite (corrected story)
<!-- inline (VERBATIM, L-0031): paste the ENTIRE contents of {story_id}-rewrite.md here. Do NOT summarize. -->
{paste the full, unabridged contents of {story_id}-rewrite.md — Gherkin in fenced code blocks}

---

## Evidence (attached)
The complete run trail is attached to this page as Markdown files:

* `{story_id}-story-input.md` — the story as received
* `{story_id}-investigation.md` — cross-referenced context (if present)
* `{story_id}-eval-report.md` — DoR scorecard
* `{story_id}-quality-gates.md` — verdict + readiness matrix
* `{story_id}-handoff.md`, `{story_id}-decision-log.md` — process trail
* (and every other `{story_id}-*.md` in the run folder)
