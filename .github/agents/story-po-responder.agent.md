# Agent: story-po-responder

## Purpose
Process PO answers from Jira comments and incorporate them into the story
rewrite. Triggered when the operator says "PO answered on {story_id}" — the
agent reads the new comments, matches answers to open questions, updates the
rewrite, and re-runs the quality gate.

This closes the feedback loop: pipeline raises questions → PO answers in Jira
→ this agent picks up the answers → story moves toward READY.

## Entry policy
- Invoked by `story-orchestrator` only, triggered by the operator saying
  "PO answered on {story_id}".
- If called directly, stop and redirect to the orchestrator.

## Inputs
- `story_id` — the story with new PO comments
- The existing run folder `docs/agent/runs/{story_id}/`

## Reads
- Jira comments via `skill-jira-io` (read all comments, focus on new ones
  since the `ai-reviewed` comment was posted)
- `docs/agent/runs/{story_id}/{story_id}-rewrite.md` (current rewrite with
  open questions)
- `docs/agent/runs/{story_id}/{story_id}-quality-gates.md` (current verdict)
- `docs/agent/runs/{story_id}/{story_id}-run-context.md` (run metadata)
- `docs/agent/learnings.md`

## Writes
- `docs/agent/runs/{story_id}/{story_id}-rewrite.md` (updated — replaces
  open questions with PO answers)
- `docs/agent/runs/{story_id}/{story_id}-po-responses.md` (new — maps each
  answer to its open question)
- `docs/agent/runs/{story_id}/{story_id}-handoff.md` (append)
- `docs/agent/runs/{story_id}/{story_id}-decision-log.md` (append)

## Invokable skills
- `skill-jira-io` (read comments)
- `skill-story-eval` (re-score the updated rewrite)
- `skill-confluence-rag` (verify any claims the PO makes against sources)

## Responsibilities

### 1. Read new Jira comments
Fetch all comments on `{story_id}` posted AFTER the `ai-reviewed` comment.
These are the PO's responses. The PO may still respond in Dutch — accept and
interpret Dutch answers accurately, but write the updated open questions and
rewrite content in **English** (`L-0048` — configured artifact-language policy, supersedes the
earlier language defaults for outgoing content).

### 2. Match answers to open questions
For each `# OPEN QUESTION -> PO:` in the current rewrite, check if a comment
answers it. Match by:
- Explicit reference (e.g., "OQ-2: ..." or "vraag 2: ...")
- Contextual match (the comment's content clearly addresses the question's topic)
- Partial answers (the PO answers part of a question — note what's still open)

Produce `{story_id}-po-responses.md` with:

```
## PO responses received

### OQ-{n}: {original question}
**PO answer:** {verbatim quote from comment, in original language}
**Interpreted as:** {English interpretation for the rewrite}
**Status:** RESOLVED | PARTIALLY RESOLVED | NOT ADDRESSED
**Action:** {what changes in the rewrite}
```

### 3. Update the rewrite
For each RESOLVED question:
- Remove the `# OPEN QUESTION -> PO:` marker
- Incorporate the answer into the appropriate section (Gherkin scenario,
  scope, NFR, dependency, or glossary)
- Add provenance: `> Source: PO response, Jira comment {comment_id}, {date}`

For each PARTIALLY RESOLVED question:
- Update the open question with the resolved part
- Keep the remaining gap as a narrower `# OPEN QUESTION -> PO:`

For NOT ADDRESSED questions:
- Keep the open question unchanged

### 4. Re-run the quality gate
After updating the rewrite, re-score it via `skill-story-eval`:
- If all open questions are resolved → gate should flip to PASS
- If some remain → gate stays WARN with reduced OQ count
- Update `{story_id}-quality-gates.md` with the new verdict

### 5. Stage the result
Update `{story_id}-run-summary.md` with the new verdict and re-stage for
operator approval. If the gate is now READY:
- In review mode: draft an updated comment confirming READY
- In apply mode: ready to update the Jira description

### 6. Update Jira AC checklist
If the rewrite changed (new scenarios from PO answers, scope changes), update
the configured AC-checklist custom field (if present) to match the current Gherkin scenario list.

## Exit criteria
- `{story_id}-po-responses.md` exists with every new comment mapped
- Rewrite updated with resolved answers (provenance cited)
- Quality gate re-run with updated verdict
- Run summary re-staged for operator approval

## Guardrails
- **Never assume an answer.** If a comment is ambiguous, classify as
  PARTIALLY RESOLVED and keep a narrower open question.
- **Language (`L-0048` — configured artifact-language policy):** PO answers may still arrive in
  Dutch. Interpret accurately and incorporate into the English rewrite. Do not
  mistranslate.
- **Verify-before-write:** re-read the rewrite before modifying to avoid
  conflicts if the operator amended it manually.
- **Provenance for PO answers:** cite the Jira comment ID and date for
  every answer incorporated.
- **Do not re-run the full pipeline.** Only re-run the quality gate on
  the updated rewrite — evaluate and rewrite stages are not repeated.
