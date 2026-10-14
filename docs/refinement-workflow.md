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
as references; they are not all automatically invoked.

## Capture, investigate and decide

1. Sign in as author. On **Requirements**, describe what needs to change and why.
   Leave Brief ID blank to generate one; keep a stable project ID.
2. In **Sources**, save relevant policy or notes. Inspect an imported issue/page
   before attaching it to the requirement. Choose whether a new version supplements
   or replaces an attached reference.
3. Connect your assistant or select a saved model on the requirement page.
   The packet contains only the selected evidence, decisions, current policy and
   output contract. A pending decision pauses further model drafting.
4. Sign in as operator. Confirm source applicability with a reason, then answer the
   next question. Each question explains why the answer affects behavior or testing.
   Resolve duplicates or scope exclusions explicitly; unanswered facts are not assumed.
5. Return to the author role and draft again using the updated context.

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
Sealed exports remain immutable, and repeat downloads return the stored bundle.

## Background model jobs

Model work runs in a bounded background executor. Refresh the requirement to see
queued, running, validating, completed, failed or interrupted status. You can cancel
before result recording; an in-flight provider may still consume compute/tokens.
Cancelled output is not applied. Once result recording starts, inspect the result
instead. Closing the application never silently retries an interrupted job.

Oversized or credential-like input fails before reserving a model attempt. Once an
attempt is reserved, provider failure, timeout or cancellation still counts against
the cycle budget. An operator may explicitly authorize another cycle with a reason.

For automation of this local workflow, the lower-level commands remain available:

```sh
python -m clarity.refine --help
python -m clarity.refine --state /absolute/private/state status --key-file /absolute/author.key --id REQ1
```

Use [recovery](recovery.md), [troubleshooting](troubleshooting.md), and the
[handoff standard](handoff-standard.md) when a step needs further detail.
