# No-tool research proposer — optional follow-up to Question Relevance Gate

This is a **model-backed research proposal**, NOT independent evidence
adjudication, owner approval, Inbox delivery, or an authorized Forge run.

## Architecture and isolation

Only a canonical GitHub Issue can be the review target. Sources must come
from a completed, provenance-bound Clarity three-stage review plus its
pinned GitHub evidence and question preview. The optional Linear packet
is read-only **historical context**; it cannot initiate work or override
approved current project decisions.

The worker is designed for a separately authenticated, reviewed Claude
CLI environment, and **does not** carry GitHub/Linear tokens or access to
GitHub Issues write, Docker, SSH, cloud infrastructure or Forge. It calls
Claude in restricted mode with no tools, no MCP, one turn, no persisted
session, a user-defined model, max-duration and max-budget arguments.
Inputs are passed only via stdin, never command arguments.

It replays the original three-stage report, source digests and question
preview **before** any paid inference, and rejects attempts to classify
questions without that evidence. It then builds one bounded prompt
containing selected reviewer questions, current revision-pinned GitHub
excerpts and optionally prior Linear extracts. No broad source search
or external website access takes place inside the model process.

The model must classify **every selected topic**, propose a concrete
reason, and include exact code/document quotations for factual answers.
The existing relevance gate checks every quoted span, source ID, topic ID
and duplicate relationship; hallucinated citations fail closed.
A model receipt must show the configured model and a fresh session ID
distinct from the original reviewer sessions.

No command in this module writes GitHub/Linear, accepts requirements,
imports to Question Inbox, acts on Docker, or dispatches Forge. Every
output explicitly marks its own classification and source authority
as **unverified**.

## CLI contract

The command below is an example of how a future isolated deployment
would run. This PR does not deploy or authenticate a runtime.

~~~bash
python3 scripts/question_relevance_research.py \
  --story /data/inputs/story.json \
  --policy /data/inputs/policy.json \
  --github-evidence /data/inputs/github-evidence.json \
  --review /data/reports/independent-review.json \
  --preview /data/reports/question-preview.json \
  --provider claude \
  --model claude-opus-5-5 \
  --start 0 --count 30 \
  --max-budget-usd 3 \
  --timeout 900 \
  --output /data/reports/research-proposal-unique.json
~~~

Use the optional --linear-history argument only when the separately
scoped historical reader and its read-only permissions have been
reviewed. Never mount a Linear token in the Claude model container.
CLI files are mode 0600 operator-private input/output.

The research script makes **at most one explicitly invoked paid model
call**, with at most 40 questions and a 120 KB prompt. A new report name
is needed for retries because outputs are exclusive-create 0600 files.
The cost cap is per CLI invocation, not a fleet-wide or monthly budget.

The output contains a model/session receipt and full proposed
dispositions, but no acceptance/notification tokens, no approved source
claims, and no right to automatically suppress or import questions.
A malformed or incomplete result refuses to write a valid proposal.

## Further work before release

1. Review PR #33 (the underlying provenance gate) and this dependent
   implementation, including independent model identity and receipt
   checks.
2. Extend the source collectors to gather focused repository paths,
   ADRs, PR discussion and authenticated historical Linear decisions
   **before** the model call. Currently the researcher's evidence
   universe is whatever was already safely collected and pinned.
3. Add independent **semantic evidence sufficiency, materiality and
   supersession verification**. An exact quote proves its presence
   in an excerpt, not that it is a complete current answer.
4. Then add a separately authenticated Inbox adapter for only genuinely
   unresolved owner decisions; keep historical/proposed dispositions
   non-authoritative and all Forge credentials outside this path.
5. Benchmark on synthetic issues first; the earlier media-update issue
   is an end-to-end pilot only, not hardcoded application behaviour.
