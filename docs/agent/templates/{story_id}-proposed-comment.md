# Proposed Jira Comment — {story_id}

Default review-mode output. Normal apply-mode approval posts no comment. Explicit
comments-only or PO-override commands follow AGENTS.md's approval matrix.

Keep this PO-facing and questions-only: verified reporter mention, unresolved
questions, and one evidence link. Findings, scores, rationale, and rewritten
requirements stay in the run evidence. Use the configured artifact language
(English by default) and the actual connector's verified comment/mention format.
Resolve account identities; never copy or guess an account ID from an example.
Suppress mentions in batch mode unless configured otherwise.

## Example — unresolved questions

```text
{verified reporter mention} — a few questions before this story can proceed:

* {specific open question 1}
* {specific open question 2}

Full review evidence: {logbook_url}
```

## Example — no open questions

```text
{verified reporter mention} — this story has been reviewed; no open questions remain.

Full review evidence: {logbook_url}
```

Publish the evidence page under the explicitly configured log-book root first;
read its real URL from `{story_id}-logbook.md`. Do not publish a placeholder link.
Only post after explicit approval and verify the result before recording success.
