# Independent question evidence challenge (proposal-only)

This is the third step of Clarity's evidence-aware question-relevance pipeline.
It requires a **GitHub Issue** review that has already passed the immutable
three-stage report checks, the offline relevance-gate replay, and the separate
read-only research proposal. Optional Linear data is **historical context**,
not a work queue, current-policy approval, or a Forge dispatch trigger.

## How it works

1. Verify all original story/policy/source packet hashes and reconstruct
   the original question topics from the three independent reviewer stages.
2. Reconstruct the first researcher's exact pinned source prompt and verify
   the researcher's batch topic IDs, model receipt and proposed dispositions.
3. Launch a **separate no-tool, single-turn, no-MCP Claude CLI session** to
   challenge the first researcher's conclusions, including the *entire*
   question, relevant qualifiers, evidence sufficiency, outdated decisions,
   materially different duplicate questions, and missing authority.
4. Verify all challenger IDs and any 12–300-character source quotations
   against pinned excerpts. Disallow a factual-answer concurrence relying
   only on GitHub issue assertions or Linear history.
5. Write an immutable, private, mode-0600 challenge report with an isolated
   model/session receipt and status per topic.

The outcomes are **CONCUR**, **DISPUTE**, and **INSUFFICIENT_EVIDENCE**.
They indicate a second model's opinion only. In particular, **CONCUR
does not mean the underlying source was refreshed, that the cited sentence
suffices as proof, or that any human decision was ratified**.

The independent challenger has no GitHub/Linear credentials, SSH, Docker,
issue writer, Inbox token, or Forge authorization. It makes at most one
explicitly requested paid model call and may use a different model ID
from the first researcher. CI tests mock the provider completely and
make no paid calls. The script is **not deployed** on R720.

## Example CLI

~~~bash
python3 scripts/question_relevance_verify.py \
  --story /private/inputs/story.json \
  --policy /private/inputs/policy.json \
  --github-evidence /private/inputs/github.json \
  --review /private/reports/review.json \
  --preview /private/reports/triage-preview.json \
  --research /private/reports/research-proposal.json \
  --provider claude --model claude-opus-5-5 \
  --max-budget-usd 3 --timeout 900 \
  --output /private/reports/challenge-unique.json
~~~

Add `--linear-history` only when the separate, scoped, read-only Linear
reader has been reviewed. Use an unprivileged isolated runtime with
operator-private input/output and no host or GitHub write permissions.

## Still required before unattended question suppression

- A separately authorized source refresher must recheck the GitHub Issue
  revision, pinned source SHA, relevant PR/ADR state and any historical
  Linear supersession and decision status.
- A trusted deterministic acceptance issuer must verify policy authority,
  meaningful sufficiency and the owner-approval boundary. Neither of the
  two AI suggestions may substitute for it.
- An Inbox integration may offer **only independently accepted, material
  unresolved owner decisions**, preserving every original stage/question ID.
  No automatic question suppression, Inbox import, policy adoption, media
  update or Forge work-order is granted by these model suggestions.

Implementation is generic; the first live media-update issue remains a
separate integration benchmark, not a built-in operational target.
