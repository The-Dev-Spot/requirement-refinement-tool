# Question Relevance Gate — offline candidate contract (v1)

Only a **canonical GitHub issue** can be the actionable target. Linear is an
optional read-only historical-context source: it may explain older work,
decisions and rationale, but cannot independently establish approved current
policy, create work, suppress a question or dispatch Forge.

## Current scope

The gate does **not** run any model, access an external API, discover sources
or apply reviewer proposals as decisions. It checks a completed Clarity
three-stage review against the exact original story, policy, pinned GitHub
source packet and privately generated question preview. It optionally checks
a separate historical Linear packet and a bounded set of **proposed**
question dispositions. All outputs are non-authoritative and private.

**Do not** feed this output directly to the existing Inbox importer. The
Inbox importer deliberately expects the original review-topic preview,
and importing it would skip source-based human triage.

### Example command (private paths are illustrative)

~~~sh
python3 scripts/question_relevance_gate.py \
  --story /private/inputs/story.json \
  --policy /private/inputs/policy.json \
  --github-evidence /private/inputs/github-evidence.json \
  --review /private/reports/three-stage-review.json \
  --preview /private/reports/question-triage-preview.json \
  --proposals /private/inputs/disposition-proposals.json \
  --linear-history /private/inputs/optional-history.json \
  --output /private/reports/relevance-candidates-unique.json
~~~

Omit optional --proposals and --linear-history until they exist.
Without proposals, all questions remain NOT_YET_RESEARCHED; no
premature owner-question routing is performed.

Files must remain private (mode 0600). The report is written with an
exclusive create: retries must use a new output filename. Run this step
offline in an explicitly reviewed context; it does not belong in the
read-only GitHub collector or with unrestricted credentials.

## Proposed disposition input contract

~~~json
{
  "schema_version": 1,
  "kind": "clarity-question-disposition-proposals",
  "target_issue": "example-org/sample-repo#123",
  "review_report_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "decisions": [
    {
      "topic_id": "topic-0123456789abcdef0123",
      "disposition": "ANSWERED_BY_GITHUB_EVIDENCE",
      "rationale": "The current pinned deployment file directly specifies the service location.",
      "answer": "The service uses a separately scoped deployment workflow.",
      "evidence": [
        {
          "source_id": "S-002",
          "quote": "a verbatim source excerpt of at least twelve characters"
        }
      ],
      "duplicate_of": null
    }
  ]
}
~~~

This illustrates the **format only**; IDs, SHA and quoted text must be
derived from the actual current review and evidence. Never invent evidence.

Four dispositions may be proposed:

- ANSWERED_BY_GITHUB_EVIDENCE requires a nonempty answer and a verbatim
  12-300-character quote from a pinned GitHub CODE, TEST or DOCUMENT
  excerpt; an issue assertion or a historical Linear claim alone cannot
  satisfy it.
- NEEDS_TECHNICAL_VERIFICATION means the answer is not established from
  available snapshots; keep researching rather than asking the owner.
- NEEDS_OWNER_DECISION means the proposer found a material decision gap.
  This is a **candidate**, not proof that research was exhaustive.
- DUPLICATE_OF names another existing, explicitly classified primary
  topic. Chained or circular duplicates fail closed, and original
  question IDs/reviewer stages are never deleted.

Proposals may cover a subset of questions. Unclassified questions remain
NOT_YET_RESEARCHED, not silently resolved. Any supplied evidence quote
must be present in the pinned source excerpt. Proposals referencing an
unknown topic/source, invalid review hash, fabricated quote, changed
historical snapshot or ambiguous duplicate relationship are rejected.

## Output and trust limitations

Output includes every original question ID, originating review stage,
source references, and a proposed disposition. It separates candidate
owner-question IDs from outstanding technical research, and explicitly
sets **all automatic question suppression, Inbox import, acceptance and
Forge dispatch authority to false**. It also requires an independent
fresh GitHub source check before acceptance.

A literal text quote verifies that the proposed evidence string is present
in the pinned source; it **does not** prove the quote answers the
question, that source content is currently true, or that an authorized
human adopted the decision. The result is an audit-ready intermediate
artifact only, not a fully autonomous Question Relevance Gate.

## Next implementation slices

1. Extend the isolated Linear historical reader with permission-scoped
   comments, status history and project mapping, and keep it separate
   from the Github collector and Claude reviewer.
2. Add a narrowly scoped research worker that can propose candidate
   answers and semantic question groups grounded in pinned GitHub and
   bounded historical context. Do not trust its classifications as
   independent verification.
3. Add an independent evidence/decision authority verifier and current
   GitHub revision check, then a dedicated reviewed adapter to present
   only genuinely unresolved owner decisions in the protected Inbox.
4. Benchmark on fictional examples and a separately collected live
   GitHub issue (for example, the previous media issue pilot). Never
   hardcode a specific repository or issue into the reusable gate.
