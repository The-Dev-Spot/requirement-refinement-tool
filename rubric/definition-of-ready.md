# Definition of Ready (DoR)

> **Status: v0.2 — WORKING DRAFT. Ratify or replace for your own project.**
> This rubric was drafted to bootstrap the toolkit and is **not yet ratified**.
> Replace it with your team's official DoR, or edit it in place. Every skill in
> this repo references this file **by path and section id** (e.g. "DoR D3"), so
> you can rewrite the content freely as long as the dimension ids (`D1`..`D10`)
> and check ids (`L1`..`L10`) keep their meaning. If you rename or renumber them,
> grep the `skills/` folder and update the references.

This is the **contract**. It defines what "ready to hand over" means for a user
story that will be built by **the receiving development team**. Everything
else in this repo enforces or references this document; nothing restates it.
See `AGENTS.md` for the standing operating rules and
`docs/adr/0001-gherkin-as-ac-format.md` for why acceptance criteria are written
the way they are.

---

## The north star: the cold-read test

A clarification channel (Slack, standup, a comment reply) technically exists,
but every time a developer has to use it, that's sprint time lost to a
back-and-forth that a clearer story would have avoided — and the alternative,
a developer quietly guessing instead of asking, is worse. So the discipline in
this rubric optimizes for the story never needing that channel in the first
place. The single question behind every dimension below is:

> **Cold-read test — Could a developer on the receiving team, with no access
> to tribal knowledge beyond what's written here, read this story once and
> build the right thing without needing to ask?**

If any part of the story only makes sense to someone "in the room", it fails the
cold-read test and is not ready. A gap discovered here is resolved **internally**
(see D6 / `# OPEN QUESTION`) — never shipped as an assumption.

---

## Story types (read this before scoring)

Not every story is behavioral, and Gherkin must **not** be forced onto work that
has no user-observable behavior. Classify the story first:

- **Behavioral** — the change is observable as system behavior (a rule, a
  calculation, a workflow, a validation, an API response). Acceptance criteria
  are **declarative Gherkin** (`Given/When/Then`). Example: "apply the
  discount rule to an order for a registered customer."
- **Non-behavioral** — enabler, spike, infrastructure, refactor, research, or
  data-migration work with no user-facing behavior to demonstrate. Acceptance
  criteria are a **measurable-outcome checklist** (see D3). Do **not** invent
  `Given/When/Then` for these.

The classification itself is part of readiness: a behavioral story hiding behind
a checklist (or an enabler contorted into Gherkin) is a D3 finding.

**Classification signal — optional `SW Development` mapping (L-0046).**
Only use this signal when the operator has configured and verified the field's
meaning for the target project. For that mapping, an unchecked value denotes
business/non-software work and a checked value indicates behavioral work unless
the content clearly says otherwise. An absent field or unset mapping is **not**
a non-behavioral signal: classify from the actual requirement, or ask the PO.

---

## Proportionality — handover payload vs. review evidence (read before scoring)

The cold-read test is about the developer finding the **right** information
quickly, not finding **all** information. A story that answers every
conceivable question in 20 KB fails the cold read as surely as a stub does —
the developer cannot see what matters. Every dimension below asks for
something to be *present*; this section sets the *ceiling*, so fixing a finding
never means "add more". See ADR-0004.

**Reference.** Use the fictional compact example in `examples/lean-requirement.md`.

### Two layers
**The split rule — build vs. justify.** The payload keeps **everything a
developer needs to build and verify** the story: what to change and where (repo,
file, chart, namespace, page), the values to use, decisions already taken,
constraints, the outcomes that define done, scope boundaries and blocking
dependencies. The review evidence keeps **why** and **where-from**: sources,
quoted rules, reasoning, precedent, alternatives considered. Lean never means
less buildable: the payload alone must pass the cold-read test for a developer
from **any** receiving development team, not only the team that wrote it.

**The budget never beats the cold-read test.** If the build-relevant content
does not fit the AC budget or size limit, **split the story** — never move
build-relevant information to the log book, and never drop an outcome to get
under 8 ACs.

- **Handover payload** — the Jira description and the AC checklist field. This
  is what the receiving developer reads. It is subject to the AC budget and size
  limits below.
- **Review evidence** — everything the pipeline needs to justify the payload:
  full citations with last-modified dates, quoted rule text, `[INFERRED from KEY]`
  precedent, risk→AC mapping and `@risk` tags, IT-proposal rationale and
  confidence, original-AC→new-AC mapping, iteration deltas, flags for human
  confirmation. It lives in the run docs (`rewrite.md` "Review notes") and the
  Confluence log book, and the payload links to it in **one line**.

### Payload shape (fixed sections; omit any that would be empty)
1. One italic line: rewritten by / date / verdict / link to the story's
   log-book evidence page, where every detail kept out of the payload is
   recorded (template in `skill-story-rewrite`; the URL is filled at write time).
2. **Objective** — 2–4 sentences (`As a … we want … so that …` for behavioral;
   objective + why for non-behavioral).
3. **Approach** (optional) — at most 5 bullets: decisions the developer must
   follow. An open IT proposal is one clause ("proposal: X; alternative: Y").
4. **Key data** (optional) — one table, only for values needed to build
   (hosts, fields, endpoints, mappings).
5. **Acceptance criteria** — the evidence rule stated **once** (e.g. "each check
   passes in TEST, INT and PROD; output pasted in one comment per
   environment"), then the ACs.
6. **Scope** — In / Out; each Out item names its owner in one line.
7. **Dependencies** — one table `Item | Status (date)`, only items that block or
   are blocked by this story.
8. **Open questions** — only if any remain.

**Never in the payload:** a glossary section; a Sources table or `> Source:`
lines; `[INFERRED from …]` tags; quoted policy text; "label/basis" columns; an
IT-proposals section with confidence ratings; sequencing/planning notes;
another story's done-condition or hand-off check; the old→new AC mapping;
step-by-step procedures already documented elsewhere (link the page instead —
only if the receiving team can open it; otherwise keep the steps the developer
must perform, in short form).

### AC budget
- **Target 3–6 ACs; maximum 8** (`L9`). A `Scenario Outline` with `Examples`
  counts as one. Needing more than 8 means the story is too big (`D7`) —
  propose a split, never a ninth AC.
- **One observable outcome per AC**: a short bold name plus one or two
  sentences. AC checklist item ≤ 250 characters (`L10`).
- **At most one illustrative command per AC**, inline. No multi-step scripts,
  exhaustive algorithm/flag lists, or `jq` pipelines — the developer writes the
  verification; the story states the outcome.
- **Negative checks are grouped by outcome.** Each relevant risk needs a
  negative check (`D5`), but one negative AC may cover several risks/paths
  (e.g. "Secure transport: `http://` returns 301; a TLS 1.1 handshake fails").
- **Recording / hand-off duties** (record a decision, post on another ticket,
  update documentation) take **at most two** ACs in total — typically
  "Decisions recorded" (before the build) and "Documented and handed over".
- No AC restates a Scope or Dependency line, or checks another story's work.
- **Fix by tightening, not adding.** A finding is closed by sharpening, merging
  or removing an existing AC first; a new AC is added only if the budget allows
  and no existing AC can carry it.

### Payload size (`L10`)
Jira description after wiki conversion: target ≤ 8,000 characters; **WARN above
10,000; FAIL above 20,000** (`L-0057`, `L-0070`; verify any platform-specific hard limit separately).
When over, move content to the review evidence; never compress the ACs into
unreadable text to fit.

---

## Dimensions

Each story is scored per dimension: **PASS / WARN / FAIL**.

- **Hard** dimensions gate readiness: **any Hard FAIL → overall FAIL.**
- **Soft** dimensions inform quality: a Soft FAIL becomes a **WARN** overall
  unless it is egregious. Some Soft dimensions **escalate to Hard** when the
  story touches their trigger (noted inline).
- The **Checked by** column tells `story-eval` which layer owns the judgment:
  `linter` (deterministic, can fail a story before any model runs), `LLM`
  (semantic), or `human` (a person must confirm; the agent can only flag).

| id | Dimension | Weight | Checked by |
|----|-----------|--------|------------|
| D1 | Cold-read independence | Hard | LLM + human |
| D2 | Story shape & value | Hard | linter + LLM |
| D3 | Acceptance criteria present & format-appropriate | Hard | linter + LLM |
| D4 | Testable & precise (no vague terms) | Hard | linter + LLM |
| D5 | Risk coverage (`@risk` -> negative scenario) | Hard | linter + LLM |
| D6 | Provenance & no invented requirements | Hard | linter + LLM + human |
| D7 | Scope & sizing | Soft | LLM |
| D8 | Dependencies & assumptions | Soft | LLM |
| D9 | Data & interface contracts | Soft (Hard if it touches an interface) | LLM |
| D10 | Non-functional & compliance | Soft (Hard in regulated flows) | LLM |

### D1 — Cold-read independence (Hard)

**Intent:** survives the cold-read test. Self-contained for a reader with no
prior context on this specific piece of work.
- **PASS:** all domain terms/acronyms are explained inline on first use or
  linked (e.g. "ISU (Internal Steering Unit)") unless they are industry-standard
  (Helm, Ingress, Terraform, TLS, …). Organization/project-specific tools, roles and names
  (an internal portal, an application identifier, a named access role, …) get a short
  inline explanation or a link, because a developer from another receiving team may
  not know them. Every referenced rule, page, screen, or system is named and
  reachable; no "as discussed", "the usual way", "see the requester". The payload has no
  glossary section — explain inline or link a page instead of restating it.
- **Payload-only cold read.** `D1` is scored on the **payload alone**, without
  the review notes or the log book. If a developer would have to open the log
  book (or ask) to know what to build, where, with which values, or how to tell
  it is done, that is a `D1` finding — move that fact back into the payload. The
  log book may answer *why*; it must never be needed to answer *what* or *how*.
- **WARN:** understandable but leans on one or two links the reader may not have
  access to; a term is expanded late.
- **FAIL:** requires internal context, undocumented jargon, or a person to
  interpret.

### D2 — Story shape & value (Hard)

**Intent:** it is clear who wants what and why.
- **PASS (behavioral):** role, capability, and benefit are present and specific
  ("As a service administrator, I want the order status synced back from the
  logistics system, so that the customer sees an accurate delivery estimate").
  Title names the behavior, not a component.
- **PASS (non-behavioral):** a clear objective and rationale ("Enable X so that
  Y becomes possible / a risk is retired").
- **WARN:** value is implied but generic ("so that it works better").
- **FAIL:** no discernible user/role, or no "so that" rationale, or the title is
  a placeholder.

### D3 — Acceptance criteria present & format-appropriate (Hard)

**Intent:** the story states, testably, what "done and correct" means, in the
**right format for its type** (see Story types above and ADR-0001).
- **PASS (behavioral):** one or more **declarative** Gherkin scenarios covering
  the happy path **and** the material alternate/error paths; scenarios describe
  *behavior and outcomes*, not UI click-scripts (see D-declarative rule below);
  within the AC budget (see Proportionality).
- **PASS (non-behavioral):** a checklist where **every item is a binary,
  observable outcome** ("Endpoint returns 200 for a valid token; schema matches
  Annex 1; migration leaves zero orphaned rows"), within the AC budget. No
  `Given/When/Then` forced.
- **WARN:** ACs present but thin (happy path only where alternates clearly
  exist), or one checklist item is not clearly binary; **or** ACs within the
  budget but padded (one outcome split across items, more than two
  recording/hand-off items, items over 250 characters, scripts instead of
  outcomes).
- **FAIL:** no ACs; or the type is wrong (behavioral story with only a checklist,
  or an enabler forced into Gherkin); or ACs are imperative UI choreography; or
  more than 8 ACs (`L9`).

**Declarative-not-imperative rule (part of D3, also see ADR-0001):** steps state
*what* the system does, not *which widget the user clicks*. Imperative verbs like
`click`, `tap`, `press`, `select ... from the dropdown`, `navigate to`, `scroll`
in a `When`/`Given` step are a D3/D4 finding. Prefer "When the order is
submitted for a registered customer" over "When the user clicks Submit".

### D4 — Testable & precise (Hard)

**Intent:** no unmeasurable language; each AC is verifiable and binary.
- **PASS:** thresholds, formats, and outcomes are concrete (amounts in EUR,
  explicit date/timeout values, exact status codes). No vague terms (see `L3`).
- **WARN:** mostly precise, one soft term that is contextually clear.
- **FAIL:** contains unquantified vague terms ("fast", "user-friendly", "handle
  errors gracefully", "as appropriate", "etc.") such that a tester could not
  write a deterministic check.

**Testable ≠ scripted.** An AC is testable when a tester can decide pass/fail
from an observable outcome (a status code, a value, a present/absent object).
An exact command is an optional illustration. Do not raise a `D4` finding on
the syntax or edge-case behavior of an example command, and do not fixture-test
example commands — writing the verification script is the developer's job.
Raise it only when the *outcome* itself is ambiguous.

### D5 — Risk coverage (Hard)

**Intent:** stories that touch a known risk prove the risk is handled.
- Every `@risk:<id>` tag on a scenario/story **must** resolve to a real entry in
  `docs/risk-register.md` (`L5`), and the story **must** contain at least one
  **negative / failure check** demonstrating the risk is mitigated (e.g. a
  rejection, a limit breach, a fallback). One negative AC may cover several
  risks. The risk→AC mapping and `@risk` tags live in the review evidence
  (`rewrite.md` "Review notes"); the payload does not need to carry the tags.
- **PASS:** all `@risk` tags resolve and each has its mandatory negative
  check.
- **WARN:** the risk is addressed in prose but the negative check is weak or
  merged into the happy path.
- **FAIL:** an `@risk` tag resolves to nothing (linter FAIL), or a risk-mapped
  story has no negative check, or a story that clearly implicates a
  register risk has no risk mapping at all.

### D6 — Provenance & no invented requirements (Hard)

**Intent:** every requirement is either sourced or explicitly open — nothing is
made up.
- **Provenance:** any claim taken from a document/spec/Confluence page cites its
  source in the canonical format (`L6`): title, section, **last-modified date**,
  and id/URL. Regulated statements (rates, ratios, rating bands) without a
  citation are a FAIL. **Where:** full citations live in the review evidence
  (`rewrite.md` "Review notes" and the log book). The payload carries the one
  evidence link, plus — only where a developer must open a source to build —
  that source's title and page id inline. A payload claim with no citation in
  the review notes is unsourced.
- **No invented requirements:** a gap becomes an explicit
  `# OPEN QUESTION -> PO: ...` marker (`L7`), **never** a fabricated `Then`
  clause or an assumed value. Open questions are resolved **internally before
  handover** (an unresolved open question is a WARN that blocks handover, not a
  silent FAIL).
- **PASS:** sourced claims are cited; gaps are open questions.
- **WARN:** unresolved `# OPEN QUESTION` markers remain (ready to review, not
  ready to hand over).
- **FAIL:** an uncited regulated claim, or a requirement that appears fabricated
  (no source, no open question) — a person must confirm suspected fabrication.

### D7 — Scope & sizing (Soft)

In-scope and out-of-scope are stated; the story is a vertical slice, not an epic.
WARN if boundaries are fuzzy; FAIL(->WARN) if it is clearly several stories —
including when it needs more than 8 ACs to state "done" (propose the split).

### D8 — Dependencies & assumptions (Soft)

Upstream/downstream dependencies, feature flags, sequencing, and stated
assumptions are listed. WARN if a likely dependency is unstated.

### D9 — Data & interface contracts (Soft; **Hard if it touches an interface**)

If the story reads/writes data or exposes/consumes an API: inputs, outputs,
schema/field definitions, example payloads, validation rules, and error
responses are specified. Missing contract detail on an interface story escalates
to a Hard FAIL. Escalation means the contract must be *covered* (a Key data
table plus ACs), not that every field or error gets its own AC — the AC budget
still applies.

**Escalation triggers (D9 becomes Hard when the story mentions any of):**
- API endpoint, REST/SOAP/GraphQL, webhook, callback
- Data feed, file import/export, batch interface, ETL
- Schema, payload, field mapping, data contract
- Integration with an external system (e.g. customer management system,
  logistics/parts system, payment gateway, retail partner application)
- Message queue, event, publish/subscribe
- Database migration, data model change

### D10 — Non-functional & compliance (Soft; **Hard in regulated flows**)

Performance, security, privacy/GDPR, auditability, data retention,
localization/currency (EUR), and regulatory constraints are addressed where
relevant. In a regulated flow an absent audit-trail / compliance criterion
escalates to Hard. A compliance requirement is folded into an existing AC where
it fits (e.g. "Secure transport" covers TLS minimum and HTTP redirect); it does
not get one AC per policy clause, and the policy text itself stays in the
review evidence.

> Apply the generic triggers below to the configured project. Add project-specific risks only from authorized sources.

**Escalation triggers (D10 becomes Hard when the story involves any of):**
- Financial transactions or invoicing (amounts, VAT/tax handling, ledger postings)
- Personal data processing (GDPR: consent, retention, right to erasure)
- Security-classified systems or data (under the applicable approved security policy)
- Payment processing or financial reconciliation
- Fraud detection, prevention, or anti-abuse controls
- Approval authority / mandate / escalation to a higher authority
- Regulatory reporting or disclosure
- Audit trail or decision logging
- Safety-relevant functionality (physical or operational safety)

---

## Deterministic checks (linter layer)

These run **before** any model. They are greppable and unambiguous, so they can
**FAIL a story on their own** (a hard-check failure short-circuits scoring). See
`.github/skills/skill-story-eval.skill.md` for how the two layers combine.

| id | Check | Fails when |
|----|-------|-----------|
| L1 | **Gherkin parses** | A behavioral story's `.feature`/AC block is not valid Gherkin (missing `Feature`/`Scenario`, steps out of `Given->When->Then` order, empty steps). |
| L2 | **Tag syntax valid** | A tag is malformed: not `@<lower-kebab>` or `@risk:<id>` / `@nfr:<id>`; unknown tag namespace. |
| L3 | **No vague terms** | An AC contains a term from the vague-term list below without an adjacent quantifier. |
| L4 | **Declarative steps** | A `Given`/`When` step contains an imperative UI verb (`click`, `tap`, `press`, `navigate to`, `scroll`, `select ... from ... dropdown`). (WARN by default; FAIL if pervasive.) |
| L5 | **`@risk` resolves** | A `@risk:<id>` does not match an entry id in `docs/risk-register.md`. |
| L6 | **Provenance format** | A line marked as sourced does not match the citation format below (missing last-modified date or id/URL). |
| L7 | **Open-question syntax** | A gap marker is not exactly `# OPEN QUESTION -> PO: <text>` (so humans can grep and promote them). |
| L8 | **Step-catalog preference** | (Advisory) A step is a near-duplicate of a canonical step in `steps/catalog.md` with different wording. WARN only — never fails. |
| L9 | **AC budget** | The payload has more than 8 ACs (checklist items, or `Scenario`s with a `Scenario Outline` counting as one). |
| L10 | **Payload size** | The Jira description is over 20,000 characters after wiki conversion (FAIL); over 10,000 characters, or an AC checklist item over 250 characters (WARN). |

**Hard linter checks** (can fail the story before the LLM runs): `L1`, `L2`,
`L3`, `L5`, `L7`, `L9`, and `L10` above 20,000 characters. `L4`, `L6`, `L8` and
the `L10` WARN thresholds raise WARNs that the semantic layer weighs.

### Vague-term seed list (L3)

Curate this with your team. A term only fails if it carries **no** adjacent,
measurable qualifier.

```
fast, quick, slow, responsive, scalable, robust, reliable, stable,
user-friendly, intuitive, seamless, simple, flexible, efficient, performant,
optimize, improved, better, enhanced, minimal, reasonable, appropriate,
as appropriate, as needed, as required, where possible, if possible,
handle gracefully, gracefully, properly, correctly, securely, etc., and so on,
and/or, some, several, various, many, few, TBD, TODO, N/A (in an AC),
support X (without stating the behavior)
```

### Canonical tag & marker syntax

- **Risk tag:** `@risk:<id>` where `<id>` matches an entry in
  `docs/risk-register.md` (id pattern `RISK-[0-9]+`).
- **NFR tag:** `@nfr:<id>` (e.g. `@nfr:audit`, `@nfr:gdpr`) — optional,
  namespaced.
- **Open question:** exactly `# OPEN QUESTION -> PO: <question>` on its own line.
  `PO` = Product Owner (the internal owner who resolves it before handover).
- **Provenance citation** (one line, directly under the claim it supports):

  ```
  > Source: <document or page title>, <section>, last-modified <YYYY-MM-DD> (<id-or-url>)
  ```

  Example — Confluence page (format only; substitute a real page when citing one):

  ```
  > Source: <Confluence page title>, <section>, last-modified <YYYY-MM-DD> (Confluence page id <NNNNNNN>)
  ```

  Example — a policy instruction grounded in `Reference/` (once populated):
  use the document's own embedded validity date (e.g. a "Status: Valid
  from ..." field), **never** the date it was converted to markdown:

  ```
  > Source: <Instruction Title>, section "<Section>", last-modified YYYY-MM-DD (Reference/<path>, "Status: Valid from YYYY-MM-DD")
  ```

  Example — an operational work-instruction extract: use the **original
  document's own date** (embedded in the filename and/or its header/body —
  e.g. an effective-date field), **never** the date the `.md` extract was
  added to this repo:

  ```
  > Source: <Work Instruction Title>, effective date, last-modified YYYY-MM-DD (Reference/<path>)
  ```

  Example — a JSON system/schema knowledge pack: use the JSON's own
  `source.export_date`-style field, **never** the date it was copied into
  this repo or "today" — the export date is what tells a reader how stale
  the schema snapshot is:

  ```
  > Source: <System> DB metadata export, table <TABLE>, last-modified YYYY-MM-DD (Reference/<path>, source.export_date)
  ```

---

## Overall gate

`story-eval` computes the gate in this order:

1. **Deterministic pre-layer.** Run `L1`..`L10`. If any **hard** linter check
   (`L1, L2, L3, L5, L7, L9`, `L10` > 20,000) fails, the overall result is **FAIL** and scoring
   stops — no model spend on a story that is mechanically broken.
2. **Semantic layer.** Score `D1`..`D10` (PASS/WARN/FAIL) with rationale and, for
   sourced claims, citations.
3. **Combine.**
   - Any **Hard** dimension FAIL (or a Soft dimension that escalated to Hard) ->
     **overall FAIL**.
   - Else any WARN (including unresolved `# OPEN QUESTION`) -> **overall WARN**
     ("ready to review internally, not yet ready to hand over").
   - Else -> **overall PASS** ("ready to hand over").

Only an **overall PASS** with **zero unresolved open questions** clears the
one-way handover bar.

---

## Related files

- `AGENTS.md` — standing operating rules (write policy, provenance, verify-before-write).
- `docs/adr/0001-gherkin-as-ac-format.md` — why Gherkin, declarative rule, risk scheme, escape hatch.
- `docs/adr/0004-lean-handover-payload.md` — why the AC budget and the payload / review-evidence split.
- `docs/risk-register.md` — the `@risk:<id>` source of truth (`L5`).
- `steps/catalog.md` — canonical step phrasings (`L8`).
- `.github/skills/skill-story-eval.skill.md` — the tool that applies this rubric.
