# Story-Quality Skill Catalog

Skills are reusable capabilities invoked by the `story-*` agents. They do **not**
own stage transitions and they do **not** decide the workflow — an agent does
that. Each skill reads its inputs, does one job, and writes only what it owns.

See `../agents/README.md` for the agents that call these skills, and
`../../AGENTS.md` for the canonical operating model.

## Core skills (always available)
- `skill-mcp-setup.skill.md` — prerequisite: verify the operator-configured authorized connector and its actual capabilities. Must succeed before any MCP-dependent skill.
- `skill-gherkin-lint.skill.md` — deterministic pre-flight (rubric `L1..L10`): parse Gherkin, validate tags, detect vague terms, resolve `@risk` ids, check open-question syntax, enforce the AC budget (max 8) and payload size. Can fail a story before any model runs.
- `skill-story-eval.skill.md` — score a story against the Definition of Ready (semantic layer + gate), consuming the lint result.
- `skill-story-rewrite.skill.md` — turn eval findings into an improved story; gaps become OPEN QUESTIONs, never invented requirements. Max 3 self-check iterations.
- `skill-story-create.skill.md` — decompose a Confluence spec/epic into candidate stories, each scored by `skill-story-eval`.
- `skill-confluence-rag.skill.md` — retrieve grounding context from Confluence / reference docs with provenance preserved (page + last-modified).
- `skill-jira-io.skill.md` — read Jira stories/boards (incl. read-only
  `find_related_issues` / `read_related_story` search for the investigator); post
  `ai-reviewed` comments (review mode), update descriptions (apply mode), or
  create a brand-new issue (`create_issue`, intake mode via `story-intake`). See
  `AGENTS.md` Write Policy.
- `skill-confluence-log.skill.md` — publish run evidence to the Confluence **log
  book**: the run-status dashboard on the root page, and one child page per story
  with the high-value artifacts inline and all raw `.md` evidence attached. The one
  bounded Confluence write; scoped to the log-book root only (`AGENTS.md` Write
  Policy → Log book).
- `skill-decision-index.skill.md` — compact append to `docs/agent/decision-index.md`.
- `skill-run-cleanup.skill.md` — repo hygiene: prune a **closed** run's local
  `docs/agent/runs/{story_id}/` folder once its evidence is verified published to
  the Confluence log book. Invoked only by the explicit "clean up closed runs"
  command; never touches Jira; never edits Confluence (read-only verification).
  See `AGENTS.md` → Repo Hygiene & Retention.

## Conditional skills (create when needed)
- `skill-feature-export.skill.md` (when a `.feature` export is in scope — see `scripts/`).

## Meta
- `skill-template.skill.md` — template for creating new skills. Not invoked at runtime.

## Shared rules
- Follow `../copilot-instructions.md` and the contract in `rubric/definition-of-ready.md`.
- Write only within the scope the calling agent requested.
- Record only non-trivial decisions to `docs/agent/runs/{story_id}/{story_id}-decision-log.md`.
- Read `docs/agent/learnings.md` before setup/tooling decisions; append reusable learnings.
- Use `{story_id}` and paths from `run-context.md` for all run artifacts.
- **No invented requirements.** A gap is an `# OPEN QUESTION -> PO:` marker, never a guessed value.
- **Cite provenance** (page/section + last-modified) for any doc-grounded claim.
