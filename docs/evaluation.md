# Evaluating requirement quality

Use `examples/quality-corpus.json`: 20 different needs, each presented as expert,
partial and plain-language input. Cases include exact boundaries, permissions,
concurrency, conflicting policies, non-functional needs, timezone ambiguity and
missing decisions. All sources and oracle expectations are synthetic and await
independent owner/developer/tester ratification. They are not measured outcomes.

## Run repeated trials

1. Pin Clarity's source revision, model/deployment, parameters and prompt version.
2. Ratify each case's agreed behavior and unresolved decisions. Do not add facts
   to compensate for an incomplete brief; all three styles share the same sources.
3. Run at least three fresh trials per case. Keep independent reviewer conversations
   separate from writer conversations. Record failed and missing runs.
4. Save actual outputs as a JSON list. A question result contains `questions` and
   `draft: null`. A completed result contains `draft` and independent `review`.

```json
[
  {
    "case_id": "booking-cancellation-plain",
    "trial": 1,
    "model": "your-exact-model",
    "result": {"questions": [{"id": "Q1", "text": "A material decision?", "why": "Its consequence", "impact": 5}], "draft": null},
    "metrics": {"elapsed_seconds": 12.5, "input_tokens": 1000, "output_tokens": 200, "correction_minutes": 0}
  }
]
```

The snippet illustrates the file shape, not a quality-labelled answer.

```sh
python -m clarity.evaluation examples/quality-corpus.json /absolute/private/trials.json --trials 3
python -m clarity.evaluation examples/quality-corpus.json /absolute/private/trials.json --trials 3 --blind-dir /absolute/private/new-blind-review
```

The report counts every expected case/trial, including missing/invalid outputs,
and separates input styles. It reports contract pass rate and observed latency
samples. A valid question response is an intermediate outcome, not a ready handoff.
No cost is guessed when usage/price evidence is absent.

Each style also reports p95 latency and sample counts, totals and medians for
reported input/output/cached tokens, model calls, revisions and correction minutes.
Metrics from invalid outputs remain in the report: failed work still consumes resources.
Absent measurements stay unknown. Record the **whole requirement's** usage, including
failed attempts and intermediate calls, rather than only its last successful call.
Use `clarity efficiency` for direct-call totals and separately record assistant-client
usage when available. Compare trials on completed handoffs and semantic ratings;
an intake advice result or small partial edit is not a final quality result. Assemble
targeted edits into the full draft before supplying the evaluation output.

## Blind review

Give reviewers the `B-*.json` packets and `ratings.csv`; retain
`PRIVATE-unblinding.json` separately. Packets omit model name, trial metadata and
original input style. Reviewers inspect actual evidence and expected behavior.
Do not show them writer confidence or model self-scores.

Have independent developer and tester reviewers record intent preservation,
unsupported claims, missed decisions, useful questions, false blocks, scenario
sufficiency and correction effort. Compare their ratings and adjudicate differences.
Report final handoff quality and useful-question quality separately. A machine
contract pass never stands in for a human semantic judgment.

The original three-case `refine.benchmark` harness remains for compatibility and
fixture regression. Neither harness claims experience invariance from synthetic
fixtures. No real trial result is shipped as if it had been executed.
