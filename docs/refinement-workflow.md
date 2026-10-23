# First run and daily use

## Install and launch

Follow the commands in the [README](../README.md). Run `clarity setup` once, then
`clarity start`. Setup is repeatable: it adds current application tables and creates
missing role keys without replacing existing state. Back up an existing workspace
before upgrading it. Unknown schema versions are rejected.

Open the exact `http://127.0.0.1:8765` address. A login key is the contents of a
private file, not its filename. Setup prints its absolute location. Use operator
for setup and decisions, author for drafting, and reviewer for independent review.
These are roles within your local workspace; they do not require three user accounts.

## Configure the workspace

As operator, open **Setup**. Prefer your existing coding assistant or add an Ollama
or local OpenAI-compatible profile. Enter its exact model ID and port, save, then
explicitly test structured output. Checks send synthetic data. An edited profile
no longer displays results from its previous configuration.

Add a source connection if needed. Otherwise the source library accepts pasted
text or UTF-8 text/Markdown files. Configure project risk IDs, reusable steps and
call/rewrite budgets in **Project quality settings**. Defaults allow six model
calls and three rewrites per cycle. The ten specialist definitions are available
as references. The three PO profiles use one shared clarification contract, also
included once in direct-model and scoped assistant author tasks. The application
does not automatically invoke all ten profiles or install native host skills.

## Capture, investigate and decide

1. Sign in as author. On **Requirements**, describe what needs to change and why.
   Leave Brief ID blank to generate one; keep a stable project ID.
2. In **Sources**, save relevant policy or notes. Inspect an imported issue/page
   before attaching it to the requirement. Choose whether a new version supplements
   or replaces an attached reference.
3. Connect your assistant or select a saved model on the requirement page.
   The packet contains only the selected evidence, decisions, current policy and
   output contract. A pending decision pauses drafting and revision; optional intake
   can reconsider which follow-ups are necessary.
4. Sign in as operator. Confirm source applicability with a reason, then answer the
   next question. Each question explains why the answer affects behavior or testing.
   Choose **Response type**: confirmed, partial, unknown, a proposal or needs
   another decision owner. Only a confirmed response settles the question.
   Resolve duplicates or scope exclusions explicitly; unanswered facts are not assumed.
5. Once pending decisions are resolved, return to the author role and draft again
   using the updated context.

For an existing draft, **Revise changed items only** returns a digest-bound edit.
Clarity assembles the full draft locally and requires a fresh independent review.
Use the complete-draft action for a larger rewrite. **Check missing decisions only**
is optional: it produces necessary new questions or intake advice, never a requirement
or approval. It may run while questions are pending. If recorded questions already
cover the gaps, it adds none and reports that decisions are still needed. Each run
is explicit and counts against the existing call budget; it does not start another
interview or automatically continue after an answer.
Complete briefs can go straight to drafting without this extra call. Profiles can
be restricted to one stage and have separate output limits; no model is selected
or escalated automatically. Inspect the estimated context budgets before running.

### Clarify what an answer actually settles

The PO Analyst investigates selected applicable evidence; the Challenger chooses
consequential questions; the Responder checks answers for conditions, gaps,
contradictions and effects on other decisions. They share the existing question and
decision history. Assistance can be more guided or concise while the final requirement
and Gherkin quality standard stays the same.

Earlier distinct responses remain visible as historical context for follow-up,
including partial information supplied before a later referral. They do not become
current decision sources. Repeated identical responses are not duplicated in model
context; the full chronological audit remains intact. Input budgets still apply,
and Clarity does not silently truncate selected context.

If an earlier response contains a mistaken sensitive paste or no longer belongs in
the selected context, an operator can open **Earlier responses (history only)** and
choose **Exclude earlier response from context**, giving a reason. Exclusion keeps
the original audit record, cannot remove a current answer or decision source, and
invalidates any existing draft/review. Correct a current response first if needed.

Questions carry stable IDs and prerequisite IDs. The live interview offers questions
whose prerequisites are resolved, ranked by impact. A foundational choice should be
asked before its dependent details; small batches suit independent decisions. Options
explain tradeoffs without making a suggested answer the default. All open questions,
including those waiting on prerequisites, continue to block drafting and handoff.

| Response kind | Meaning | Question/source effect |
| --- | --- | --- |
| `confirmed` | The operator records an authorised business answer. | Settles the question and supplies an authoritative decision source. |
| `partial` | Part of the decision is understood; a material remainder is unresolved. | Keeps the question open; records context without decision authority. |
| `unknown` | No answer is known yet. | Keeps the question open without assuming a value. |
| `proposal` | An option is suggested but not confirmed. | Keeps the question open; the suggestion cannot support an approved rule. |
| `needs_owner` | A suitable decision owner must supply or confirm the answer. | Keeps the question open; an optional owner label helps route the question. |

For example, “Probably, but operations needs to confirm” belongs in a proposal or
needs-owner response. It does not establish the cancellation rule. An optional
decision-owner label is descriptive; it does not authenticate that person or give
them workspace access. Models may flag an apparently incomplete or contradictory
confirmed answer, but only the operator records its disposition.

When a confirmed prerequisite changes, affected confirmed dependent questions reopen
for reconfirmation. Their previous answers remain in the audit history and visible
context, but cannot support the current draft until reconfirmed. New questions use
new IDs; existing questions need an explicit operator merge or scope resolution.
No model can silently remove a question because it now appears unnecessary.

A useful example-mapping session starts with the agreed rule, then asks for one
ordinary example, a refusal/exception, an exact boundary and an alternative path.
Use the question form for any missing business decision. The draft's coverage table
shows which scenarios cover each category and why a category may not apply.
An empty category requires a reviewed explanation; every rule still needs a scenario.

## Review and handoff

The draft shows narrative statements, their exact supporting quotations, Gherkin
and a coverage table. Inspect the before/after comparison and quality findings.
Syntax success alone does not mean that the requirement is correct.

Use a different reviewer identity and a fresh assistant conversation. The reviewer
checks every statement and scenario, challenges ambiguity, and evaluates intent,
precision, scope, dependencies and non-functional needs. Failed or incomplete checks
return the requirement for revision. A writer's self-assessment is not an independent review.

As operator, select Cucumber, Xray Cloud or Xray Server/DC and inspect the exact
proposed files. Approve that handoff, then **Seal and get approved handoff** within
15 minutes. A changed source, answer, policy or review requires fresh approval.
Sealed exports remain immutable. The default download contains two delivery files:
`requirement.md` and `acceptance.feature`. Individual downloads are also available.
Open **Full evidence and audit download** for the source text, traceability,
review and manifest. Both views use the same approved bytes; neither generates
additional model output or deletes the audit history.

## Background model jobs

Model work runs in a bounded background executor. Refresh the requirement to see
queued, running, validating, completed, failed or interrupted status. You can cancel
before result recording; an in-flight provider may still consume compute/tokens.
Cancelled output is not applied. Once result recording starts, inspect the result
instead. Closing the application never silently retries an interrupted job.

Oversized or credential-like input fails before reserving a model attempt. Once an
attempt is reserved, provider failure, timeout or cancellation still counts against
the cycle budget. An operator may explicitly authorize another cycle with a reason.
Configured token-budget and exhausted-rewrite preflight failures also avoid a model
call. The [efficiency guide](efficiency.md) explains estimates and reported usage.

For automation of this local workflow, the lower-level commands remain available:

```sh
python -m clarity.refine --help
python -m clarity.refine --state /absolute/private/state status --key-file /absolute/author.key --id REQ1
```

Use [recovery](recovery.md), [troubleshooting](troubleshooting.md), and the
[handoff standard](handoff-standard.md) when a step needs further detail.
