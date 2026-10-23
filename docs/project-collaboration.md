# Project language, stakeholder questions and portable handoffs

These are optional local operator tools. Clarity remains standalone: no development
pipeline client, dispatch action, remote publication or new model permission is
introduced. The existing workbench, compact default download, source limits,
independent review and exact approval/sealing controls remain unchanged.

Glossary approval and questionnaire/portable exports are available through
`python -m clarity.refine`. The live PO interview also supports prerequisite ordering
and explicit response kinds in the workbench. A selected glossary appears in the
existing Sources view and reaches assistants through the normal selected-evidence
path. Never give an assistant the operator key or private controller workspace.

## Approve reusable terms, select exact revisions

Create a small JSON glossary in an operator-controlled location:

```json
{
  "schema_version": 1,
  "reason": "The project owner confirms these definitions describe the agreed business domain.",
  "terms": [{
    "id": "TERM-CANCEL",
    "term": "Cancellation",
    "definition": "Stopping a queued operation before it begins.",
    "aliases": ["Cancel"]
  }]
}
```

Prefer terms that prevent a real ambiguity. Record architectural decisions in the
existing approved project sources rather than filling a glossary with every detail.
Term names and aliases must be unique after case/whitespace normalization. Stable
term IDs identify concepts; changing a definition requires a new approved revision.

```sh
python -m clarity.refine --state /private/clarity glossary \
  --key-file /private/operator.key --project PERSONAL

# Use the displayed record; zero means no glossary exists yet.
python -m clarity.refine --state /private/clarity approve-glossary \
  --key-file /private/operator.key --project PERSONAL \
  --expected-record 0 --input /private/glossary.json

# Substitute the actual requirement version, returned record and digest.
python -m clarity.refine --state /private/clarity attach-glossary \
  --key-file /private/operator.key --id REQ1 --version 1 \
  --record APPROVED_RECORD --digest DISPLAYED_DIGEST
```

Approval is operator-only, append-only and guarded by the previous record number.
Selecting a revision is another explicit operator action. It becomes a normal
versioned reference source, subject to the existing source-count/byte budgets.
An author or model cannot promote definitions to trusted evidence.

Updating the project glossary does not silently rewrite any requirement. To adopt
a later revision, explicitly attach it and supply `--replace-source GLOSSARY-OLD_RECORD`
when replacing a previous selection. Old records remain in the audit history.
Changed selected evidence invalidates the current draft/review/approval through the
existing context digest. Starting new requirements without a glossary is still valid.

## Ask the person who holds the decision

Use the existing interview to distinguish discoverable facts from consequential
owner decisions. Read selected evidence before re-asking. Resolve prerequisite
choices before dependent ones; ending an interview is not proof of completeness.
The shared [PO clarification contract](../.github/skills/po-clarification/SKILL.md)
gives the Analyst evidence investigation, the Challenger question selection and the
Responder answer interpretation within one continuing history.

When the current requester lacks knowledge or authority, export only the relevant
open questions for a suitable stakeholder:

```sh
python -m clarity.refine --state /private/clarity questionnaire \
  --key-file /private/author.key --id REQ1 \
  --recipient "Business owner" --purpose "Resolve cancellation exceptions" \
  --questions Q1 Q2 --dependencies /private/dependencies.json \
  --output /private/cancellation-questions.md
```

Questions persist their own `prerequisites` array. The live interview offers questions
whose prerequisites are settled and ranks eligible questions by impact. Export
inherits these dependencies. The optional file is an explicit overlay for that
questionnaire, for example `{"Q2":["Q1"]}`; it does not change stored questions or
live ordering. The helper rejects unknown references, duplicates and cycles, follows
merged targets and orders questions by prerequisite then impact. Already answered
or explicitly out-of-scope prerequisites do not need to be re-asked. An omitted open
prerequisite is flagged by ID rather than silently treated as answered.

The document contains stable question IDs, selected question text/consequences,
recipient role, purpose, requirement version and context digest. It does not attach
source bodies or export the entire brief. Review it before sharing; question text
can itself be sensitive. Return answers through the existing operator answer/source
confirmation workflow, not automatic import. New evidence still requires normal
revision and independent review.

Record the nature of each returned answer explicitly. For example, an operator may
record this response JSON without treating it as a confirmed business rule:

```json
{
  "question_id": "Q1",
  "answer": "Operations must confirm whether a running report can be cancelled.",
  "response_kind": "needs_owner",
  "decision_owner": "Operations owner"
}
```

```sh
python -m clarity.refine --state /private/clarity action answer \
  --key-file /private/operator.key --id REQ1 --version CURRENT_VERSION \
  --input /private/answer.json
```

Supported response kinds are `confirmed`, `partial`, `unknown`, `proposal` and
`needs_owner`. Only `confirmed` answers become decision sources and settle questions;
the others remain open. The optional owner label identifies a routing need, not an
authenticated person. Existing callers that omit `response_kind` retain the previous
confirmed-answer behavior; new clients should send the kind explicitly. Questions
from older clients may omit `prerequisites`; model task schemas require an array,
empty when no prerequisite exists.

Earlier distinct responses are retained as historical context, without decision
authority. To exclude one from future model tasks, the operator can use the browser
history action or `action exclude-response-history` with JSON fields `question_id`,
`response_digest` and `reason`. The digest must match the entire selected item in
`response_history`; the reason must explain the exclusion. This affects only earlier
context, preserves the original immutable audit and requires fresh drafting/review.

Changing a confirmed prerequisite reopens affected confirmed dependent decisions
and removes their current decision-source authority until reconfirmation. The audit
history remains intact. Use a new question ID for a necessary follow-up; model calls
cannot silently merge or remove existing questions. An explicit, budgeted intake
call can reconsider pending gaps, but draft and revision calls remain blocked while
any question is open. The questionnaire export itself never mutates or resolves them.

## Optional portable view of an existing seal

The normal handoff still contains only `requirement.md` and `acceptance.feature`.
The full private audit ZIP remains separate. A recipient that needs revision and
scenario integrity can receive this third, explicitly selected view:

```sh
python -m clarity.refine --state /private/clarity portable \
  --key-file /private/author.key --id REQ1 --approval SEALED_APPROVAL_ID \
  --output /private/REQ1-portable.zip
```

This reads an existing sealed bundle through authenticated controller access; it
does not approve or seal a draft, call a model, upload data or start development.
It produces exactly three files: the two unchanged delivery files plus `handoff.json`.
Metadata contains contract version, requirement/revision, export profile, upstream
digests, payload SHA-256 hashes and stable scenario IDs. It omits source bodies,
operator/reviewer identities, credentials and permissions. Gherkin bytes and line
endings remain exactly those approved. Repeating the export on the same interpreter
produces the same ZIP bytes without another model call.

The contract kind is `clarity-portable-handoff`, integer `schema_version: 1`.
Recipients independently enforce their own trust, execution and publication policy.
Hashes do not authenticate a sender or prove that a business statement is true.
Do not send the audit ZIP merely because a recipient needs integrity metadata.

## Scope and qualification

The helpers adapt composable engineering practices from
https://github.com/mattpocock/skills without vendoring its prompts or installing an
auto-updating orchestration framework. No provider-specific model is required.

Tests cover operator-only glossary approval/selection, optimistic concurrency,
immutable revision selection, stale-review invalidation, questionnaire dependencies,
private-source omission and exact-byte exports. Contract tests do not establish
semantic model quality, reduced token cost or a live downstream execution benchmark.
