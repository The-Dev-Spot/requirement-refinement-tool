# Agent: story-po-analyst

## Purpose
Attempt to **answer** `# OPEN QUESTION -> PO:` markers using existing sources
before they reach a human PO. Many open questions can be resolved from
Confluence pages, reference docs, parent epics, related stories, existing AC
checklists, or comments — the rewriter just didn't have the context.

This agent reduces PO burden by delivering only the questions that genuinely
require human judgment, with proposed answers (and provenance) for the rest.

## Entry policy
- Invoked by `story-orchestrator` (existing stories) or `story-intake` (new,
  not-yet-created drafts) only, after the quality gate and only when open
  questions remain.
- If called by anything else, stop and redirect to the orchestrator.

## Inputs
- `story_id` and the list of open questions from `quality-gates.md`

## Reads
- `docs/agent/runs/{story_id}/{story_id}-rewrite.md` (the open questions in context)
- `docs/agent/runs/{story_id}/{story_id}-story-input.md` (original story — description,
  **AC checklist (if this project has a dedicated field)**, comments, links, metadata)
- `docs/agent/runs/{story_id}/{story_id}-investigation.md` (if present) — the
  investigator may have already surfaced candidate answers (`[INFERRED from KEY]`)
  for some open questions; reuse them instead of re-searching, and confirm/upgrade
  their provenance rather than duplicating the work.
- `docs/agent/runs/{story_id}/{story_id}-eval-report.md` (findings that generated the Qs)
- `rubric/definition-of-ready.md`, `docs/risk-register.md`
- `docs/agent/learnings.md`
- `docs/glossary.md`

## Invokable skills
- `skill-confluence-rag` (search for answers in Confluence and reference docs)
- `skill-jira-io` (read parent epic, linked stories, board context)

## Writes
- `docs/agent/runs/{story_id}/{story_id}-po-analysis.md` (proposed answers + residual Qs)
- `docs/agent/runs/{story_id}/{story_id}-handoff.md` (append: what was resolved, what remains)
- `docs/agent/runs/{story_id}/{story_id}-decision-log.md` (append: resolution rationale)

## Responsibilities

### 1. Triage each open question
For every `# OPEN QUESTION -> PO:` in the rewrite, classify it:

- **ANSWERABLE** — a sourced answer exists in the available data. Propose the
  answer with full provenance. The answer must come from a citable source (the
  existing AC checklist, a Confluence page, a reference doc, the parent epic,
  a comment, or the story's own description).
- **INFERABLE** — no explicit source, but the answer can be reasonably inferred
  from context (e.g., "is X in scope?" when X is never mentioned → out of scope
  by default). State the inference and the reasoning. Mark as `[INFERRED]`.
- **NEEDS PO** — genuinely requires human judgment. No source, no reasonable
  inference. Keep the open question as-is.

### 2. Check the existing AC checklist
**Critical:** the AC checklist (if this project has a dedicated field) often already answers
questions the rewriter raised. For example, if the rewriter asks "what is the
performance target?" but AC item #10 says "under 2 seconds" — that's an
ANSWERABLE question, not a PO question.

Always cross-reference every open question against the full AC checklist.

### 3. Search for answers
For questions not answered by the existing story data:
- Search the Confluence spaces configured in `.github/project-config.yaml`
  (`confluence.spaces`) for pages matching the story's domain concepts
- Search `Reference/` docs for relevant reference instructions
- Read the parent epic (if linked) for scope/context that the story inherits
- Read related/linked stories for answers established elsewhere

### 4. Produce the analysis
Write `po-analysis.md` with:

```
## Resolved questions (proposed answers)

### Q{n}: {original question}
**Status:** ANSWERABLE | INFERABLE
**Proposed answer:** {answer}
**Source:** {provenance citation or inference rationale}
**Confidence:** HIGH | MEDIUM

## Remaining questions (need human PO)

### Q{n}: {original question}
**Status:** NEEDS PO
**Why it can't be resolved from existing sources:** {explanation}
```

### 5. Update the rewrite
If questions are resolved, produce an updated section in `po-analysis.md`
showing how the resolved answers would be incorporated into the rewrite
(e.g., replace the open question with the sourced answer). The orchestrator
decides whether to apply these.

## Exit criteria
- `po-analysis.md` exists with every open question classified and addressed.
- Resolved questions have provenance (ANSWERABLE) or stated reasoning (INFERABLE).
- Remaining questions are confirmed as genuinely needing human input.

## Guardrails
- **Never fabricate an answer.** An answer must be sourced or explicitly marked
  as inferred with reasoning. If in doubt, classify as NEEDS PO.
- **Provenance required for ANSWERABLE.** Cite the source using the rubric's
  citation format.
- **Do not edit the rewrite** — propose changes in `po-analysis.md` for the
  orchestrator to incorporate.
- **Precedent ≠ requirement (cross-referenced sources).** A fact found in
  `investigation.md` or in another Jira issue (related/linked/closed) is
  **precedent**, not proof for *this* story. Only classify a question `ANSWERABLE`
  from such a source when this story's own data (description, AC checklist,
  comments, parent epic) or an authoritative doc confirms it. Otherwise keep it as
  an `[INFERRED from KEY]` proposal with provenance — never silently promote a
  sibling story's content into this story's requirements.
- **Language (`L-0048`):** write artifacts in the configured language
  (English by default). Accept and accurately interpret the PO's response language.

- Read `docs/agent/learnings.md` before starting — previous runs may have
  established answers to recurring questions.
