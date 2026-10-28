# Story-Quality Agent Catalog

Agents own lifecycle and accountability for improving a Jira story to the point it
can be handed to **the receiving development team** without a clarifying
question. They invoke skills (`../skills/`) for capabilities; they do not
inline that logic.

## Run modes
The orchestrator supports two modes, set once at run start:
- **review** (default) — ends in a questions-only `ai-reviewed` comment; the rewrite stays in the run evidence.
- **apply** — writes the rewrite directly to the Jira description when the quality
  gate is `READY`. No comment is posted.

A third mode, **intake**, belongs to `story-intake` (not the orchestrator): a
not-yet-created draft runs the same pipeline and ends with `create_issue`
instead of a comment/description write, only after explicit approval.

## Autonomous agents (story-quality pipeline)
- `story-orchestrator.agent.md` — owns the run, stage transitions, and mode.
  Posts comment (review) or updates description (apply).
- `story-investigator.agent.md` — INVESTIGATE stage (between READ and EVALUATE):
  cross-references related/closed Jira issues (links, epic siblings, clones,
  component/label) and Confluence child pages / data dictionaries; writes cited
  `investigation.md`. Precedent ≠ requirement — foreign facts are `[INFERRED from
  KEY]`, never invented requirements. Callable by `story-orchestrator` or
  `story-intake`.
- `story-evaluator.agent.md` — scores the story against the Definition of Ready.
  Callable by `story-orchestrator` or `story-intake`.
- `story-rewriter.agent.md` — drafts the improved story (max 3 iterations;
  runs only if evaluate is not PASS). Callable by `story-orchestrator` or
  `story-intake`.
- `story-quality-gate.agent.md` — final handover-readiness verdict. In review
  mode, drafts the `ai-reviewed` comment. In apply or intake mode, records the
  verdict only. Callable by `story-orchestrator` or `story-intake`.
- `story-po-analyst.agent.md` — attempts to answer open questions from existing
  sources (Confluence, reference docs, AC checklist, epic, comments). Runs only when
  open questions remain after the quality gate. Callable by `story-orchestrator`
  or `story-intake`.
- `story-po-challenger.agent.md` — challenges whether open questions are
  necessary, well-formed, or can be converted to proposals. Runs alongside the
  analyst. Callable by `story-orchestrator` or `story-intake`.
- `story-po-responder.agent.md` — processes PO answers from Jira comments.
  Matches answers to open questions, updates the rewrite, re-runs quality gate.
  Triggered by "PO answered on {story_id}".

## Standalone agents
- `story-creator.agent.md` — propose a story breakdown from a Confluence
  spec/epic (invoke directly; always review mode).
- `story-intake.agent.md` — conversational front door for a **single, brand-new**
  requirement (conversational intake): interviews a business stakeholder
  (conversation language chosen by the stakeholder; configured artifact language out), then runs the draft through the same
  investigate/evaluate/rewrite/quality-gate stages before a human approves
  creating the Jira issue. If the conversation turns out to be about an
  existing item, it hands off to `story-orchestrator` instead of drafting a
  duplicate.

## Skills
Skills live under `.github/skills/` and are invoked by the agents above.

## Entry policy
- **Pipeline**: invoke `story-orchestrator` only. Stage agents
  (`investigator`, `evaluator`, `rewriter`, `quality-gate`) are invoked by
  `story-orchestrator` **or** `story-intake` — not direct entrypoints; if
  called by anything else, they stop and redirect to the orchestrator.
- **Standalone**: `story-creator` and `story-intake` can be invoked directly at
  any time.
- Runtime doc behavior is defined in `runtime-doc-contract.yaml`
  (`workflow` for the orchestrator, `intake_workflow` for `story-intake`).

## Execution order (pipeline)
1. Operator provides a story id (or pasted story) and optional `mode: apply` to
   `story-orchestrator`.
2. Orchestrator reads the story (`skill-jira-io`) and gathers context
   (`skill-confluence-rag`), writing `run-context.md` and `story-input.md`.
3. Orchestrator expands a `detailed-plan.md` with `INVESTIGATE` / `EVALUATE` / `REWRITE` / `VERIFY` sections.
4. Orchestrator runs `story-investigator` (INVESTIGATE) — cross-references related/
   closed Jira issues and Confluence child pages; writes cited `investigation.md`.
5. Orchestrator runs `story-evaluator` (EVALUATE) — reads `investigation.md`.
6. If the gate is not PASS (or open questions remain), orchestrator runs
   `story-rewriter` (REWRITE, max 3 iterations) — also reads `investigation.md`.
7. Orchestrator runs `story-quality-gate` (VERIFY) — re-scores the final story.
8. **If open questions remain:** orchestrator runs `story-po-analyst` +
   `story-po-challenger` (PO ANALYSIS) to answer/challenge them, then re-runs the
   quality gate if anything changed.
9. Orchestrator stages the result in `run-status.md` and waits for operator to
   **approve**, **approve + apply** (review-mode READY only), **approve with open
   questions** (NOT-READY override), **PO answered**, **amend**, or **deny**.
10. **On approve — review mode:** posts the `ai-reviewed` comment.
   **On approve — apply mode:** updates the Jira description (if `READY`).
   **On amend:** incorporates changes, re-runs quality gate, re-stages.
   **On deny:** closes the run as `rejected`.
11. Close as `done` only when READY, zero open questions, and the approved Jira
    outcome is written. A posted questions comment or override with unanswered
    questions remains `awaiting_po`; comments-only on READY stays staged for
    a later approved description write. `deny` closes as `rejected`.

## Execution order (intake)
See `story-intake.agent.md` for the full procedure. Summary: interview the
stakeholder (with an early existing-item/dedup check) → draft under a temporary
run id → run the same investigate (always DEEP)/evaluate/rewrite/quality-gate
stages directly → **PO analysis whenever open questions remain** (same
`story-po-analyst`/`story-po-challenger` treatment a review-mode run gets,
plus an intake-only option to loop back to the stakeholder directly) → stage
for approval (`approve` / `approve with open questions` / `amend` / `deny` —
no `approve + apply` or `just add comments`, nothing exists yet to promote
into) → on approval, `create_issue`, publish the log book, update
`decision-index.md` (mandatory, full parity with a review-mode run), then
migrate the run folder to the real Jira key and rejoin the standard pipeline
lifecycle above.

## Required docs
See `../../AGENTS.md` ("Docs Ownership") for exact write ownership, and
`docs/agent/templates/` for canonical run-document structure.
Use `docs/agent/learnings.md` as the single shared learnings register.
