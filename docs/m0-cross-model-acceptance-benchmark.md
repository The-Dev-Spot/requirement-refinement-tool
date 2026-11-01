# M0 first review and cross-model acceptance benchmark

**Status:** executable provider-neutral comparative **QA harness**. This is
not a production-ready trusted acceptance gate, not a live authenticated
Claude/Opus result and not a model-independent proof of semantic correctness.

## Why this exists

The same requirement must be judged against the **same frozen source, owner
decisions, source authority, D1–D10 rubric and L1–L10 rules** whether the
reviewer is ChatGPT, Claude Opus, Sonnet or another model. Different wording
is okay; different acceptance of a material contradiction is **not**.

Clarity uses model-generated evidence to help find flaws. The acceptance
decision comes from deterministic policy, tested provenance and authorized
project decisions. A model never gets to decide its own tool permissions,
source authority, approval identity or production-critical classification.

## Initial two real reference cases

1. **M0 conflict — [HOM-1972](https://linear.app/sashafelix-homelab/issue/HOM-1972).**
   Latest source observed on 2026-11-01 at revision
   `2026-11-01T07:15:35.085Z`, compared against
   [HOM-1973](https://linear.app/sashafelix-homelab/issue/HOM-1973)
   revision `2026-10-31T23:38:28.136Z`.
   Material **expected findings**: an older two-total-worker/global-one-model
   rule versus the current **four worker container slots across two independent
   Clarity/Forge pools**; and older human-start gate versus current **no per-job
   Start after authorized n8n intake**. Review must distinguish a one-job
   supervised *pilot* from unattended production architecture. Expected:
   **BLOCKED / NEEDS_DECISION** for implementation acceptance.
2. **Positive case — Forge's shipped disposable
   [first-change example](https://github.com/The-Dev-Spot/forge/blob/main/examples/first-change/plan-input.md).**
   The approved-in-principle illustrative behavior is `greet()` remains
   `Hello!`, `greet("Ada")` returns `Hello, Ada!`, input whitespace is
   stripped, blank names raise `ValueError`, and tests use Python unittest.
   Expected **clean candidate only** once independent reviews, actual local
   model sessions, exact ZIP binding, source and policy approval are verified;
   no production or authenticated auto acceptance here.

**Do not publish entire private Linear issues or project policies** to the
public Clarity repository. Public CI uses a fully synthetic analogue of both
examples. Real source snapshots and human-reviewed gold examples belong
in an access-controlled project workspace. A gold example requires owner
approval and a pinned digest; it is *not* an arbitrary LLM-produced answer.

## Executable comparison

`scripts/benchmark_review_consistency.py` compares **two to eight** preexisting
quality-review packets, regardless of which model produced them. Each report
must follow Clarity's existing three-stage output schema. This script
**does not call models**, infer real model identity or authenticate claimed
session metadata.

Example with files frozen in a **private** workspace:

```bash
python3 scripts/benchmark_review_consistency.py \
  --story /private/clarity/HOM-1972.snapshot.json \
  --policy /private/clarity/forge-city-policy.json \
  --gold /private/clarity/HOM-1972.gold.json \
  --review chatgpt=/private/clarity/HOM-1972.chatgpt.json \
  --review opus=/private/clarity/HOM-1972.opus.json \
  --output /private/clarity/HOM-1972.comparison.json
```

`gold.json` format:
- `schema_version: 1`, `case_id`;
- raw file `source_sha256`, `policy_sha256`, and
  `rubric_sha256` for the **complete authoritative version** of
  `rubric/definition-of-ready.md`;
- `expected_aggregate`: `BLOCKED` or `REVIEWABLE_CANDIDATE`;
- `source_anchors`: precise substrings that must occur in the frozen source;
- `required_findings`: each has `id`, short audited regex `aliases`, and
  `required_stages` drawn from investigator/evaluator/challenger.

The scorer **recomputes** reviewer stages with Clarity's
`quality_review.check_stage` and `summarize`.
It also requires a matching rubric digest in both the report and every
stage receipt, distinct session IDs and requested/resolved model consistency.
Model IDs remain provider-reported rather than independently attested; this
benchmark detects missing/mismatched claims, not maliciously forged identities. It never trusts an agent's
reported top-level aggregate, claimed READY or later version of the source.
It fails when either result misses a gold-standard blocker or when their
computed outcomes differ. A difference in narrative phrasing alone should not
fail. These regex labels are a *regression aid*, not proof of business semantics
or immunity to gaming by models.

The output is `PASS` or `FAIL` for the **benchmark only** and always
`ready_for_handover: false` and `publication_authority: false`.

## Local and CI proof

`tests/test_benchmark_review_consistency.py` uses two **synthetic
simulated reviewer outputs**, not paid ChatGPT/Opus calls, to assert:
- Same source/policy + distinct model phrasing, same clean or blocked outcome.
- Contradictory-worker-capacity and manual-start findings detected from both
  investigator and cold challenger.
- Missing one known material finding causes benchmark FAIL even when another
  blocker keeps the overall verdict BLOCKED.
- Missing D dimensions, stale source, changed policy, claimed READY and
  linter WARN cause benchmark FAIL.
- The comparison outcome cannot create an accepted requirement or grant tools.

## Before treating any real review as equivalent across providers

1. Freeze exact source issue and owner-approved source hierarchy; approve
   and pin the project-specific gold rubric before benchmarking (not retroactive).
2. Actually run independent ChatGPT and Claude Opus review sessions with
   the same immutable input, prompt/rubric, context budget and declared
   applicable check set. Local Claude Code runner supports only its own
   authenticated Claude client; ChatGPT model results need a separate
   authorized adapter producing the same schema.
3. Retain true runner identities, model versions, timestamps, tool boundary,
   source hashes and usage receipts from **trusted orchestration**, not
   model-supplied strings. Mark missing receipts NOT_VERIFIED.
4. Compare each provider with the gold, compute per-finding recall/precision,
   unresolved contradictions and any drift. Re-run after any source/rubric/
   policy/model adapter revision. Do not silently merge competing answers.
5. Use `scripts/accept_requirements.py` for non-authorizing source/ZIP proposal
   checks, then the future authenticated policy service for ACCEPTED. No
   autonomous Forge implementation starts from this QA benchmark.

**Immediate gap:** no authenticated Opus CLI or ChatGPT-to-Clarity evaluation
adapter is exposed in this ChatGPT environment. We can validate the source and
run synthetic CI benchmarks now, but may not assert that two real model
providers agreed. The HOM-1972 live independent reviewer and the real Forge
greeting-change implementation remain to be executed on an authorized host.

Related: [HOM-1983](https://linear.app/sashafelix-homelab/issue/HOM-1983),
[HOM-1982](https://linear.app/sashafelix-homelab/issue/HOM-1982).
