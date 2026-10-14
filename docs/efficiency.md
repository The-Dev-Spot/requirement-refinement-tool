# Efficient use of Clarity

Start with a complete draft, independently review it, resolve material findings,
then approve and seal. Optional stages help when needed; they never run automatically.

## Choose the smallest useful action

| Action | Use it for | Result |
| --- | --- | --- |
| Complete draft | A new brief or substantial rewrite | Questions or a full draft |
| Targeted revision | Corrections to an existing draft | Questions or changed items only |
| Intake questions | An early check of missing business decisions | Questions or advisory readiness to draft |
| Independent review | Checking the complete current draft | Every required statement, scenario and semantic assessment |

Targeted revision preserves unchanged text and IDs. Null title/feature/proposals
means unchanged; statement/scenario edits use stable IDs and coverage uses
statement ID plus category. Changed Gherkin is returned as a complete feature to
preserve formatting, Rules, Backgrounds, tables and Examples. The base draft digest,
workflow version and current context must match. Unknown removals, duplicate edits
and no-op revisions are rejected. The controller validates the assembled full draft;
an edit cannot waive a finding or reuse the previous independent review/approval.

Resolve pending owner decisions before another model call. Batch related answers
before resuming. Select relevant original source excerpts with their applicability;
never replace authoritative evidence with an unverified generated summary.

## Configure models and limits

In **Setup → Models & assistants → Efficiency and stage settings**, optionally
restrict a profile to intake, drafting, revision or independent review. This allows
a smaller model for intake and a separately evaluated model for review. Select the
profile explicitly on the requirement page; there is no automatic provider fallback.
All profiles still meet the same final handoff standard.

The complete-draft output limit is the profile's main output setting. Intake,
revision and review have their own limits. Older profiles keep their existing
draft/revision/review limit and use at most 1024 output tokens for optional intake.
An output limit is a ceiling, not tokens automatically consumed. Set a limit large
enough to complete the contract; truncation remains a failure without automatic retry.

Set **Server context capacity** to the token window actually configured on your
deployment, or leave it at 0 when unknown. The pre-run table estimates input from
UTF-8 bytes divided by three, adds 512 tokens for wrappers, and reserves the selected
output limit. It includes the system instruction and one native schema. This is a
portable estimate, not the model's tokenizer or a guarantee against server truncation.
An over-budget estimate blocks before reservation; no selected evidence is dropped.
For Ollama, the configured capacity also sets `options.num_ctx`. Other local servers
need their own context configuration. Larger windows can consume more memory.

## What gets smaller

Direct transports put the output schema in the native API field once. They do not
repeat it in the prompt. Assistant task packets retain one schema because clients
need the contract. The original request appears once as source BRIEF. Prompts retain
all selected evidence, decisions, authority and policy, the exact feature and all
required review criteria. They omit expanded validation examples already represented
by the feature, repeated machine results in review feedback and illustrative schemas
that duplicate the actual schema. Reviewers never receive the writer's previous verdict.

Fixed evidence is sent before changing drafts/feedback for prefix reuse. **Cloud
prompt cache → Explicit stable prefix** adds an Anthropic `cache_control` breakpoint
or OpenAI `prompt_cache_options`/`prompt_cache_breakpoint`. The OpenAI explicit form
requires a compatible API/model (documented for GPT-5.6 and later); use **Provider
default** for other models. Test structured output after changing the setting.
Cache thresholds, lifetime, schema changes and deployment behavior affect reuse;
cache writes can cost extra. Measure total cost rather than assuming a cache hit.
Ollama keep-alive avoids repeated loading when possible; it is separate from prompt
caching and token capacity. Clarity does not control a coding assistant's cache.
Native schemas avoid embedding the changing draft digest as a schema enum; the
controller still checks its exact supplied value. Schemas can remain stable across
text edits when statement/scenario IDs and warning fields are unchanged.

## Read the efficiency measurements

The requirement page shows finished direct attempts, revisions, measured input,
output and cached tokens, elapsed inference time and totals by stage. Failed and
cancelled attempts count when the provider reports their usage. Totals cover the
whole requirement history, even across new cycles; detailed recent calls show the
latest 12 attempts. OpenAI nested cache/reasoning counts are retained; Anthropic's
uncached input plus cache reads/writes is normalized for input totals. A reasoning
count is a subset of output, never added twice.

Missing measurements stay unknown. Partial totals state how many attempts reported
usage. Unfinished reservations remain visible and their unreported usage is unknown.
Assistant submissions are counted, but their conversation tokens and time
are outside Clarity's telemetry. Costs and human correction effort are not guessed.
Read the same scorecard as JSON:

```sh
clarity efficiency --state /absolute/private/state --key-file /absolute/private/author.key --id REQ1
```

Compare total calls/tokens and correction effort **per completed requirement**,
including failed attempts and retries. Record actual deployments and repeated
[evaluation trials](evaluation.md). A smaller prompt is a byte measurement, not
proof of token savings or unchanged semantic quality.

## Deliver two files, retain the evidence

The default sealed download contains `requirement.md` and `acceptance.feature`.
The full private audit download adds sources, traceability, quality review, import
notes and the manifest. Both are deterministic views of the same sealed approved
bytes, generated locally without another model call. Audit records remain stored.
The lower-level seal CLI accepts `--full-audit` for the seven-file evidence ZIP.

## Protocol references

- [OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)
- [Anthropic prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Ollama context capacity](https://docs.ollama.com/context-length)
- [Ollama chat options and usage](https://docs.ollama.com/api/chat)
