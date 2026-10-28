# Run Summary — {story_id}

> One-page overview of the pipeline result. Read this first — it links to the
> detail files if you need to go deeper.

## Story
- **Key:** {story_id}
- **Title:** {title}
- **Type:** {behavioral | non-behavioral}
- **Status:** {Open | In Progress | ...}

## Pipeline result

| Stage | Gate | Key outcome |
|-------|------|-------------|
| READ | {✅ | ❌} | {what was found — stub? ACs? comments?} |
| EVALUATE | {PASS | WARN | FAIL} | {top findings} |
| REWRITE | {PASS | WARN | n/a} | {what changed} |
| QUALITY GATE | {READY | NOT READY} | {verdict} |
| PO ANALYSIS | {done | n/a} | {questions resolved / remaining} |

## Verdict: {READY | NOT READY}
{one-line summary of why}

## Open questions for PO ({count})
{numbered list of remaining open questions — short form}

## What will happen on approval
- **Review mode:** {post ai-reviewed comment to {story_id}}
- **Apply mode:** {update description of {story_id}}

## Operator action
> **approve** / **approve + apply** (READY, review) / **just add comments** / **amend** / **deny**

## Run files
| File | Purpose |
|------|---------|
| `story-input.md` | Original story as received |
| `eval-report.md` | Full DoR scorecard |
| `rewrite.md` | Improved story |
| `quality-gates.md` | Final verdict + readiness matrix |
| `proposed-comment.md` | Draft Jira comment |
| `po-analysis.md` | PO question answers (if run) |
| `po-challenge.md` | PO question challenges (if run) |
| `handoff.md` | Stage-by-stage log |
| `decision-log.md` | Non-trivial decisions |
