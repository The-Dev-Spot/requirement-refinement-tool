# Skill: skill-story-rewrite

## Purpose
Turn `skill-story-eval` findings into an improved story that aims to clear the
Definition of Ready gate — tightening vague ACs, adding missing negative
scenarios, expanding jargon, restoring provenance — **without inventing anything
that was not there**. Invoked by `story-rewriter`.

## Reads
- `rubric/definition-of-ready.md`, `docs/risk-register.md`, `steps/catalog.md`
- `docs/agent/runs/{story_id}/{story_id}-story-input.md` (original story + context)
- `docs/agent/runs/{story_id}/{story_id}-eval-report.md` (the findings to address)
- Cited Confluence/reference context (via `skill-confluence-rag`) for concrete rules

## Writes
- `docs/agent/runs/{story_id}/{story_id}-rewrite.md` (the improved story; write-once),
  in two sections:
  - `## Jira payload` — exactly what goes into the Jira description and AC
    checklist, in the payload shape of rubric "Proportionality". Budgeted. Its
    first line is always the evidence-link line, with the URL left as the
    placeholder `{logbook_url}` (filled by `skill-jira-io` at write time from
    `{story_id}-logbook.md`):
    `_Rewritten by Clarity on <YYYY-MM-DD> (<verdict>). Sources, rationale, risk mapping and investigation: [<story_id> review evidence|{logbook_url}]._`
  - `## Review notes (run docs only — not posted)` — citations, quoted rules,
    `[INFERRED from KEY]` precedent, risk→AC mapping, proposal rationale,
    original→new AC mapping, iteration deltas, flags for human confirmation,
    and any detail the subtractive pass moved out of the payload. Published
    verbatim to the log book, so it must be complete.
- `docs/agent/runs/{story_id}/{story_id}-decision-log.md` (append: what changed and why)

### Standards-grounded rewrite

Use `Reference/standards/README.md` only for the *applicable* concerns surfaced
in investigation/evaluation (APPLIES / UNKNOWN with cited reason). Convert a
confirmed missing behavior into one **measurable** positive/negative outcome
within the existing 3–6 AC target and eight-AC hard maximum; merge or split
rather than add generic "secure/accessibile/scalable" criteria. If a standard
recommends a control but the project has not adopted its exact target,
mark `# OPEN QUESTION -> PO:` in the draft and keep reference rationale in
review notes. Never claim a test, certification or legal verdict without evidence.

## Steps
1. **Assess completeness.** If the story is a stub (minimal description, no ACs),
   this is a **draft-from-context** rewrite, not a polish. Use the gathered context
   in `story-input.md` — Confluence pages, reference docs, parent epic, comments,
   labels, feature team — to reconstruct the story. Search clues: the title often
   names the capability; the epic/parent provides scope; comments may contain the
   original intent. Every claim must be sourced; what cannot be sourced becomes an
   open question.
2. **Confirm the story type** (behavioral vs non-behavioral). Do not change a
   story's type to make it easier to write — behavioral stories get declarative
   Gherkin; enablers/spikes get a measurable-outcome checklist (rubric `D3`).
3. **Address each finding** in priority order (hard blockers first). **Tighten,
   merge or remove an existing AC before adding one**; add a new AC only if the
   budget (rubric "Proportionality", max 8) allows and no existing AC can carry it.
   - *Vague term (`L3`/`D4`)*: replace with the concrete rule **only if a cited
     source states it**; otherwise raise an open question.
   - *Missing negative path (`D3`/`D5`)*: add the failure outcome — preferably
     into an existing negative AC grouped by outcome; record the `@risk:<id>`
     mapping in the review notes.
   - *Cold-read gaps (`D1`)*: expand an unfamiliar acronym inline once; name/link
     every rule and system referenced. No glossary section.
   - *Provenance (`D6`)*: put the citation (with last-modified) in the review
     notes; the payload keeps only the evidence link and, where needed to build,
     a page title + id.
   - *Contract/NFR (`D9`/`D10`)*: add inputs/outputs/errors or audit/compliance
     criteria **only** where a source supports them — as a Key data table or
     folded into existing ACs; else an open question.
4. **Prefer catalog steps.** Reuse an existing `steps/catalog.md` phrasing before
   writing a new step; if you must add one, write it declaratively and propose it
   for the catalog (`steps/README.md`).
5. **Keep it declarative** — behavior and outcomes, never UI clicks (ADR-0001);
   state the observable result, not the verification script.
6. **Record open questions** for every gap you could not close from a source, as
   `# OPEN QUESTION -> PO: <specific, answerable question>`.
7. **Subtractive pass (mandatory, before every hand-back).** First apply the
   **keep test** to every item: *does a developer from any receiving team need this to
   build or verify the story?* If yes, it **stays** in the payload (shorten it,
   don't move it). Only content that answers *why* or *where-from* is cut — and
   cut means **move, never delete**: everything cut
   goes to the review notes, which (with the attached run docs) are published
   verbatim on the story's log-book page and are the full record:
   - anything on the rubric's "Never in the payload" list → review notes;
   - ACs that restate scope, dependencies, or another story's done-condition;
   - two ACs that test the same outcome → merge; recording/hand-off duties → at
     most two ACs;
   - commands beyond one short illustrative command per AC;
   - background the developer does not need in order to build.
   If the content that passes the keep test still breaks the budget, propose a
   split — never move build-relevant content out to fit.
   Then measure: AC count (≤ 8, target 3–6), each checklist item ≤ 250 chars,
   payload ≤ 8,000 chars target (WARN > 10,000, FAIL > 20,000 after wiki
   conversion). Record the counts in the decision log.
8. **Hand back** for re-scoring — `story-quality-gate` re-runs
   `skill-story-eval` on the rewrite.

## Iteration cap
The rewriter self-checks with `skill-story-eval` after each draft. **Maximum 3
iterations.** If the story has not reached PASS or WARN-with-only-open-questions
after 3 iterations, the rewriter stops and hands back the best draft with residual
findings logged. Each iteration's delta and gate result must be recorded in
`decision-log.md`. **An iteration must not grow the payload**: if the payload is
longer or has more ACs than the previous iteration, justify each addition in the
decision log or cut it.

## Output quality rules
- Every change traces to a finding; every unclosed gap is an open question.
- No citation dropped while rewriting (citations move to the review notes, they
  are not deleted); no claim added that cannot be sourced.
- Reuses catalog step phrasings; new steps are declarative and vague-term-free.
- The payload meets the rubric "Proportionality" budget and the fictional compact example.

## Guardrails
- **The one hard rule: never invent a requirement to make a story pass.** A guess
  becomes the receiving team's silent, unrecoverable error.
- No stage ownership; `story-rewriter` owns the transition.
- Output is a draft for the quality gate — the rewriter never writes to Jira directly.
