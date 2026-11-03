# GitHub evidence → Clarity review triage (issue #172, offline first slice)

This change creates **a private, read-only preview**, not a second
requirements engine or a new way to approve work.

### Why a separate preview?

The first successful R720-AI GitHub collection against
`The-Dev-Spot/homelab#169` generated two citations and an evidence
packet marked `SOURCE_UNVERIFIED`. Its story and policy were simplified
*smoke-test inputs*. In particular, the policy does not yet contain the
ACTIVE, scope-matched decision register required by Clarity's independent
review contract. That is entirely appropriate for proving GitHub API
access, but not grounds for asking Opus to approve an actual requirement.

### What the module does

`scripts/preview_github_review.py` takes a private story, policy,
GitHub-only v2 evidence packet, and optionally an independently completed
Clarity review report.

- Validates packet hashes, repo allowlists, scope, issue reference, source
  digests and source URL/revision shape.
- Reports whether the **structural** project review-policy contract passes.
  This does **not** verify who approved any decision or that a source is
  still current.
- Without a completed review, shows citations and a `NOT_RUN` state,
  proposes zero owner questions, and highlights that the current policy
  needs refinement. This is the expected path for the original #169 smoke test.
- With a review, requires all three *raw file hashes* to match the
  independent report's input/policy/evidence hashes. It reuses the existing
  reviewer question-export contract, keeps original question IDs and
  producing stages, groups **only** case/whitespace/trailing-punctuation
  equivalent questions, and suggests high-overlap alternatives **without
  merging them**.
- Extracts explicit `S-001`-style citations only if cited in question
  text; missing references remain `NOT_CITED` and unknown references
  fail validation. It does not assert that a cited source resolves the
  question. No raw source excerpts are placed in the preview.
- Writes a new operator-private mode-0600 JSON file. It never sends
  Slack, imports questions, writes a GitHub Issue, invokes an LLM,
  grants `ACCEPTED_FOR_FORGE`, or changes the Question Inbox.

### Operator preview after updating the pinned R720 image

Assuming the original two private inputs and the GitHub-only evidence packet
are still present, choose the exact evidence filename from the successful
collection. Do **not** commit, share, or paste that private packet.

```sh
cd /opt/homelab/stacks/clarity-context-collector

# Set to the private evidence filename already created by the successful run.
EVIDENCE_FILE="issue-169.<actual-timestamp>.evidence.json"
OUT="issue-169.$(date -u +%Y%m%dT%H%M%SZ).triage-preview.json"

docker compose run --rm --no-deps -T --entrypoint python3 collector \
  /opt/clarity/scripts/preview_github_review.py \
  --story /inputs/issue-169.story.json \
  --policy /inputs/issue-169.policy.json \
  --evidence "/evidence/$EVIDENCE_FILE" \
  --output "/evidence/$OUT"
```

Expected: `review=NOT_RUN`, `topics=0`, with a private report
showing `policy_review_contract=NOT_READY`. Do not attempt to pass a
historical HOM-1972 review report to this new GitHub issue: the issue
identity, scope and content hashes must differ.

### Before generating real questions

1. Capture the **full current GitHub issue** and the explicit, owner-selected
   project policy/decision register; distinguish the issue narrative from
   adopted requirements. Generate a new story/policy-bound evidence packet.
2. Complete the separate authorized Clarity review using those exact
   inputs. A valid model response is a *proposal*, never owner policy.
3. Use `--report /private/<completed-review-report>.json` to produce a
   question-topic preview. Keep the reviewer report private, including
   stage receipts and findings. Verify topic citations and decisions
   before any Inbox import or owner-facing notification.
4. Extend the Question Inbox to support these source-aware topic records,
   including issue revision and all original question IDs. The current Inbox
   import schema does **not** support this preview; pretending it does
   would lose provenance. That is a separate tracked integration step.
5. Only a separately authenticated acceptance issuer may advance an
   approved issue to Forge after the source has been revalidated.

The previous 27-question Linear pilot is **historical**. It is not
imported as GitHub current requirements or automatically answered.

Tracking: [homelab #172](https://github.com/The-Dev-Spot/homelab/issues/172).
