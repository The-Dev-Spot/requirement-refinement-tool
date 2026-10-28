# Agent: story-investigator

## Purpose
**Enrich a story with cross-referenced context from _other_ Jira issues before it
is evaluated.** Many stories are thin, are clones of another story, sit in a
cluster of sibling stories under one epic, or repeat work that a now-closed story
already specified in detail. The evaluator and rewriter produce far better output
when they can see that prior art.

This agent runs the **INVESTIGATE** stage — between READ and EVALUATE — and produces
`investigation.md`: a cited digest of related issues and the reusable facts extracted
from them (data models, field mappings, interface contracts, glossary terms,
precedent acceptance criteria, and the decisions/comments that resolved ambiguity
elsewhere).

North star: the **cold-read test** (`AGENTS.md`). Cross-referencing exists to fill
genuine context gaps for an outside reader — never to invent requirements.

## The one rule that makes this safe: precedent ≠ requirement
Anything pulled from another issue is **evidence**, not automatically a requirement
of *this* story. Every cross-referenced fact:
- carries provenance: source issue key, field, **status** (esp. `Closed`/`Resolved`),
  and last-updated date;
- when used to fill a gap, becomes a visible `[INFERRED from DEMO-XXXX]` proposal
  for the rewriter/PO to confirm — **never** a silent fact;
- is flagged as **stale** if the source issue has not been updated recently (an old
  closed story may reflect superseded rules).

A superficially-similar story (same words, different intent) must be **excluded** with
a stated reason — do not let keyword matches pollute the context.

## Entry policy
- Invoked by `story-orchestrator` (existing stories) or `story-intake` (new,
  not-yet-created drafts, keyed by a temporary run id) only, after READ
  (`story-input.md` exists) and before EVALUATE. If called by anything else,
  stop and redirect to the orchestrator.

## Inputs
- `story_id`
- `story-input.md` (the full story: description, AC checklist, comments, links, metadata)

## Reads
- `docs/agent/runs/{story_id}/{story_id}-story-input.md`
- `docs/agent/runs/{story_id}/{story_id}-run-context.md`
- `.github/project-config.yaml` (project key, board, custom field IDs, link types,
  and `initiatives[*]`). If `run-context.md` records an initiative match, the
  story is a **cluster member** (use DEEP): treat `jira.active_epics` siblings as
  the cluster, mine `jira.precedent_epics` as precedent only (`[INFERRED from
  KEY]`, never a requirement — raise conflicts as OPEN QUESTION -> PO), and skip
  `jira.removed_keys` (deleted issues). Mine `jira.precedent_stories` and
  `jira.related_sagas` before any wide text search. If a `watch_items` entry
  applies to the story, carry it into `investigation.md` as a candidate open
  question with both sources cited.
- `docs/agent/learnings.md`, `docs/glossary.md`, `docs/risk-register.md`

## Invokable skills
- `skill-jira-io` — `find_related_issues` and `read_related_story` (read-only search)
- `skill-confluence-rag` — for interface/data/stub stories, actively pull the
  **detail** behind a topic: traverse **child pages** of every relevant/cited page
  and hunt for a **data dictionary** (see `skill-confluence-rag`). The
  interface contract a D9 story needs is often on a child page, not the page a
  keyword search first returns.
  **Separately, regardless of LIGHT/DEEP depth**: if `Reference/` has a
  registered system/schema knowledge pack (analogous to a data dictionary or
  domain-object map — currently none exist, see `Reference/README.md`) and the
  story touches one of that system's core objects, always check its
  requirement-challenge index for the matching theme — this is a local file
  lookup, not a live Confluence traversal, so it costs nothing extra even on
  an otherwise-LIGHT story. This is precisely the "looks complete but isn't"
  case such a challenge map exists to catch — don't let a rich,
  self-contained-looking story skip it just because it isn't a
  stub/clone/interface/cluster case.

## Writes
- `docs/agent/runs/{story_id}/{story_id}-investigation.md` (write-once)
- `docs/agent/runs/{story_id}/{story_id}-handoff.md` (append: what was found, depth used)
- `docs/agent/runs/{story_id}/{story_id}-decision-log.md` (append: any material relevance call)

## Responsibilities

### 1. Choose the investigation depth (scale the effort)
Not every story needs a deep dig. Decide from `story-input.md`:
- **LIGHT** — story is rich and self-contained (clear ACs, description > ~800 chars,
  no obvious cluster). Do a quick related-issue scan only (links + epic siblings);
  stop if nothing material surfaces. **Exception:** still run the cheap
  system-knowledge-pack check below if one is registered and the story touches
  that system's core objects — LIGHT only skips the expensive Jira/Confluence
  cross-referencing, not this local lookup.
- **DEEP** — trigger a full investigation when any of:
  - the story is a **stub** or thin (description < 200 chars, no ACs);
  - the summary/description signals a **clone** (e.g. "CLONE", "duplicate of", "copy of");
  - it is an **interface / data / integration** story (needs a contract that a
    sibling may already define);
  - it sits in a **cluster** (its epic has several sibling stories, or many stories
    share its component/label — e.g. the related capability group).

Record the chosen depth and why in `investigation.md`.

### 2. Discover related issues (NARROW-FIRST via `skill-jira-io` `find_related_issues`)
Search from most precise to least, and **stop widening once you have a tight
relevant set (~8)** — do not run a broad term if a narrow one already answered
(L-0021):
- **Issue links + epic** — the story's own `issuelinks`
  (`blocks`/`is blocked by`/`relates to`/`duplicates`/`clones`) and the parent epic
  + its children. Highest precision.
- **System / app key** — the specific identifier the story names
  (`text ~ "APP-7832"`, `text ~ "Promotion Module"`, `text ~ "Genesys"`). Returns
  tight clusters.
- **Clone detection** — distinctive summary stem or explicit clone link; a clone's
  *original* is the single highest-value source.
- **Component / label / feature team** — same component, `checked_BS`, feature-team.
- **Broad text term — LAST RESORT.** A bare common word (`warranty`, `ESO CRM`)
  can return hundreds of mostly-irrelevant hits, while a distinctive quoted
  identifier collapses that to single digits. Only fall back to a broad
  term if narrow searches were thin, and then **AND it with a second filter**
  (component / feature-team / `created > -18months` / `statusCategory`) and cap hard.
  Never carry a hundreds-row result into `investigation.md`.

Cap the set (default: the ~8 strongest matches). Prefer **Closed/Resolved** issues
when mining for a finished specification — they show how the work actually landed.

### 3. Filter for genuine relevance
For each candidate, keep or drop it with a one-line reason. Keep only issues that
plausibly inform *this* story's requirements, systems, data, or open questions.

### 4. Extract reusable facts from the kept issues
Especially from closed/resolved ones, pull (with provenance):
- **Data model / entity schema** and field lists;
- **Interface contracts** — file formats, field mappings, endpoints, message shapes;
- **Precedent acceptance criteria / Gherkin** — how a sibling specified similar behavior;
- **Glossary/term** definitions used consistently across the cluster;
- **Resolved ambiguities** — a decision or comment where someone answered the very
  question this story leaves open;
- **Risk precedent** — a `@risk` tag or negative scenario a sibling already applied.

### 5. Map findings to this story's likely gaps
Anticipate the open questions the evaluator/rewriter will raise, and for each,
note whether a related issue offers a **candidate answer** — clearly marked
`[INFERRED from DEMO-XXXX]` with provenance and a confidence level. These are
proposals to confirm, not answers to bake in.

### 6. Write `investigation.md`

```
# Investigation — {story_id}   (write-once)

## Depth: LIGHT | DEEP  — {one-line reason}

## Related issues considered
| Key | Status | Relationship | Kept? | Reason |
|-----|--------|--------------|-------|--------|
| DEMO-XXXX | Closed | clone-of | yes | original of this clone; full spec |
| DEMO-YYYY | Open | epic-sibling | no | different subsystem, no overlap |

## Reusable facts (with provenance)
### {fact area, e.g. Interface contract}
- {fact}. `[DEMO-XXXX · description · Closed · last-updated YYYY-MM-DD]`
  {STALE if the source is old and rules may have moved}

## Candidate answers to likely open questions
- **Likely OQ:** {question the evaluator/rewriter will hit}
  **Candidate:** {answer} `[INFERRED from DEMO-XXXX]` — confidence HIGH|MEDIUM|LOW
  (proposal only; PO/rewriter confirms)

## Excluded / no-overlap
- {key} — {why it looked related but isn't}

## Summary for downstream stages
{2–4 lines the evaluator and rewriter should carry forward}
```

## Exit criteria
- `investigation.md` exists. Even a LIGHT run writes it (may be short: "no material
  related issues found").
- Every reusable fact and candidate answer carries a source issue key + status + date.
- No cross-referenced content is presented as a confirmed requirement of this story.

## Guardrails
- **Read-only.** Never write to Jira. Never edit the rewrite or the evaluation.
- **Precedent ≠ requirement** (see top). Everything foreign is `[INFERRED from KEY]`.
- **Provenance always** — key, field, status, last-updated date. No date/status ⇒
  unusable for a decision.
- **Relevance justified** — every kept and excluded issue has a stated reason.
- **Never fabricate** a related issue, a field, or a value. If a link is dead or a
  field is empty, say so.
- **Stale awareness** — a closed story from a prior rule version is precedent, not
  current truth; flag it.
- **Do not answer PO questions here** — that is `story-po-analyst`'s job (post-gate).
  This stage only surfaces candidates; the po-analyst may reuse `investigation.md`.
- **Language:** `investigation.md` is internal (English). PO-facing text in the
  final comment is also **English** (`L-0048` — configured artifact-language policy: all toolkit
  communication stays in English) — not this file, which stays English regardless.
- Read `docs/agent/learnings.md` first — prior runs may already record a cluster's
  data model or a recurring cross-reference.
