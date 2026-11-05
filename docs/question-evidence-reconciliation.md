# Trusted question-evidence reconciliation (offline, blocked)

`scripts/reconcile_question_evidence.py` binds the PR #33 provenance gate,
PR #34 research proposal and PR #35 independent challenge to an authenticated
read-only GitHub collector receipt. It does not run any model or API and does
not connect to the Inbox, approval issuer, issue writer or Forge.

## Trust boundary

Unsigned JSON containing `MATCHED_AT_READ_TIME` is not trusted evidence. The
collector can now emit a domain-separated HMAC-SHA256 envelope over its own
readback, the exact independent challenge digest, and its read interval.
The reconciler requires this envelope and an independently configured secret.
It rejects a bad MAC, future/expired interval, changed source, wrong review,
missing source, repeated source, mismatched revision or scope, and authority
claims. Every source must match, and the canonical GitHub target must be present.

The secret is separate from the GitHub read token. A future authorized operator
must provision a cryptographically random secret (at least 32 bytes of key
material), stored in an owner-only file, **only in the trusted collector and
reconciler**. No real key is generated or installed by this change. Both HMAC
holders can mint receipts; this is a symmetric trust boundary, not public-key
non-repudiation. Neither process may run untrusted PR code with that secret.
The model runtime must never receive it or the GitHub/Linear credentials.

The collector signs only after performing its own GitHub reads; there is no CLI
that signs an externally submitted readback. Old unsigned collector output is
still available for diagnostics but is rejected by reconciliation. The receipt
authenticates source readback, not the origin or correctness of model claims.
Model/session receipts are replayed for consistency; they are not converted
into authenticated semantic authority by this signature.

Freshness is limited to the recorded read interval. The default allowed age is
300 seconds from the **start** of collection; trusted operator configuration
can select 1–900 seconds. A new reconciliation or downstream operation must
check freshness again. The stored report is not a reusable authorization token.
Issue checks establish `updated_at` and excerpt presence, plus consistency of
bounded discussion during the read. The existing packet does not retain a full
original discussion digest, so this does not establish that every uncited
comment is unchanged since original collection. Repository checks conservatively
require the original pinned commit to remain the actual default-branch HEAD.

## Replay and result

Reconciliation first reconstructs the three-stage preview and the researcher's
exact prompt, selected batch, quotations and dispositions. It then reconstructs
the independent challenge prompt and checks model identity fields, unused
session ID, topic coverage, quotations, counts and all false authority flags.
`CONCUR` with outstanding missing evidence is contradictory and rejected;
`INSUFFICIENT_EVIDENCE` must name the missing evidence.

| Research/challenge result | Reconciliation status |
|---|---|
| Unselected topic | `NOT_YET_RESEARCHED` |
| `DISPUTE` | `DISPUTED` |
| `INSUFFICIENT_EVIDENCE` | `NEEDS_RESEARCH` |
| Answer + `CONCUR` | `SUPPORTED_ANSWER_CANDIDATE` |
| Owner decision + `CONCUR` | `OWNER_DECISION_CANDIDATE` |
| Technical verification + `CONCUR` | `NEEDS_TECHNICAL_VERIFICATION` |
| Duplicate + `CONCUR` | `DUPLICATE_CANDIDATE` |

Every topic remains in `unresolved_topic_ids`. Originals, reviewer stages,
source IDs, answers, rationales and independent assessments remain visible.
Duplicates retain their primary's status, including disputed or unresearched
primaries; they never hide a blocker. Candidate owner IDs are for private
review only and cannot be imported to the Inbox.

GitHub Issues remain the only actionable intake. Optional Linear history is
revalidated against the exact GitHub story/policy and model prompts and remains
`HISTORICAL_UNVERIFIED`, with no current-policy or intake authority. Linear-only
factual resolution is rejected. This change does not add Linear API reads,
comments/status collection or writes.

Overall status is always `BLOCKED`. Authenticated snapshot matching does not
establish semantic completeness, supersession, deployment state, current owner
authority or policy adoption. Independent semantic/materiality/authority checks
and a protected Inbox adapter remain outstanding. Approval, question suppression,
Inbox import and Forge dispatch authority remain false.

## Future authorized invocation (not executed or deployed)

First, the separately authorized collector rechecks sources after the challenge
already exists. This command makes GitHub reads, with no model use:

~~~sh
python3 scripts/recheck_github_sources.py \
  --story /private/story.json --policy /private/policy.json \
  --github-evidence /private/github.json \
  --github-key-file /private/secrets/github-read.key \
  --challenge /private/challenge.json \
  --attestation-key-file /private/secrets/collector-attestation.key \
  --output /private/freshness-unique.json
~~~

Then the trusted reconciler runs offline, without provider credentials:

~~~sh
python3 scripts/reconcile_question_evidence.py \
  --story /private/story.json --policy /private/policy.json \
  --github-evidence /private/github.json --review /private/review.json \
  --preview /private/preview.json --research /private/research.json \
  --challenge /private/challenge.json --freshness /private/freshness-unique.json \
  --collector-key-file /private/secrets/collector-attestation.key \
  --max-age-seconds 300 --output /private/reconciliation-unique.json
~~~

Supply the same optional `--linear-history` packet used by the research and
challenge stages, if any. Private inputs and outputs require owner-only files.
Output uses exclusive creation, mode 0600. Exit 0 means a blocked report was
successfully produced; it never means READY, approval or dispatch permission.
Invalid inputs exit 3 without a new report. CI uses synthetic keys and mocked
providers only; no paid models or R720 deployment are involved.
