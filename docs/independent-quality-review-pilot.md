# Running Clarity's independent quality-review pilot

**Status:** local experimental read-only runner. The deterministic L1–L10 checker and Clarity→Forge handoff are merged and CI-tested. The **three-session semantic pipeline** in `scripts/quality_review.py` runs only when explicitly invoked on a machine with an authenticated, recent Claude Code CLI. It has no Jira, Linear, Forge, production, Docker or GitHub write capability. It does not automatically declare READY.

## What runs

1. Node-based L1–L10 preflight using Clarity's pinned Cucumber parser, optional operator-selected approved risk register, and stable input hash. A mechanical FAIL/BLOCKED or missing approved policy **stops before model usage**.
2. Separate **investigator** `claude -p` call receives source story + the project policy snapshot.
3. Separate **evaluator** `claude -p` call receives the same story/policy and the investigator's report; it produces evidenced D1–D10 PASS/WARN/FAIL/NOT_RUN.
4. Separate **challenger** `claude -p` call receives the original story + policy **without** the investigator's or evaluator's output. It challenges ambiguity, contradictions, source authority, failure cases, security and test oracles.
5. The **Python aggregator**, not an agent, blocks on unresolved conflicts, missing required evidence, open questions or disagreement. Even three clean sessions yield `REVIEWABLE_CANDIDATE` rather than a fabricated final READY or permission to write.

Each invocation uses `--restricted`, `--tools ""`, `--disallowedTools mcp__*`, `--permission-mode dontAsk`, `--no-session-persistence`, `--max-turns 1`, `--output-format json`, and `--json-schema`. No Bash, web, connected apps, write/edit tools or MCPs are accessible inside the evaluation. Run on a trusted machine, not inside an untrusted PR job. Project data is sent to the authenticated model provider, so only provide policy-approved data.

**Anthropic reference:** [Claude Code CLI](https://code.claude.com/docs/en/cli-reference). `--restricted` requires a recent release (v2.1.248+). Check your installed CLI version and current authentication/usage terms before running. `--max-budget-usd` uses estimated spend and can exceed its client-side limit; on subscription accounts, don't infer API billing from the flag. Never collect or broker another user's Claude account tokens. No model invocation occurs in Clarity's GitHub CI.

## What to prepare

1. **A frozen story snapshot**, stored privately, formatted as the input understood by the [L1–L10 checker](../.github/validation/quality-gate.mjs). For infrastructure/research, provide `story_type: non-behavioral`, `payload`, `title`, and a list of typed outcome `criteria`; for behavioral work, supply a Gherkin `feature`. Keep the source issue ID + revision + links in the story's payload/review notes. Do not invent new ACs simply to make the snapshot pass.
2. **A project policy snapshot**, stored outside the public repository: `project`, `adopted` (must be true and operator-approved), `risk_register_status: APPROVED`, `risk_register_path` to a local approved Markdown risk register, plus `decisions` each with exact `id`, `source`, `revision`, `authority` and `text`. An example with fictional sources is given below.
3. **A private output folder** outside git-tracked paths. The tool creates one JSON report with restrictive file permissions. Input source and model output may contain confidential information; use your existing secure private retention policy.

Example policy shape (fictional — NOT an approved Forge City policy):

```json
{
  "project": "SYNTHETIC",
  "adopted": true,
  "risk_register_status": "APPROVED",
  "risk_register_path": "/private/approved-risks.md",
  "decisions": [
    {
      "id": "ADR-EXAMPLE-1",
      "source": "Approved synthetic policy",
      "revision": "v1",
      "authority": "product owner",
      "text": "One normal and one reserved critical worker in each independent pool."
    }
  ]
}
```

## Command

```bash
# On the trusted host, with Node 24, Python 3.12, a current Claude Code
# installation authenticated by its own login flow, and approved project data:
npm ci --ignore-scripts --prefix .github/validation
python3 scripts/quality_review.py \
  --input /private/forge-city/HOM-1972.snapshot.json \
  --policy /private/forge-city/project-policy.json \
  --output /private/forge-city/HOM-1972.review.json \
  --provider claude --model sonnet --max-budget-usd 1.00
```

For **synthetic offline tests only**, use `--provider fixtures --fixture-dir /private/fixtures`, with separate `investigator.json`, `evaluator.json`, `challenger.json` files. Synthetic fixture reports remain **BLOCKED** regardless of simulated PASS results.

The report contains input/policy hashes, actual preflight result, invocation IDs and model-provided output/metadata, plus a machine-derived aggregate. It does **not** attest that input policy was approved by a cryptographically verified owner or that model findings were factually correct. These require a trusted supervisor and human adoption before advancing to automatic Forge City dispatch.

## First M0 pilot

Use **HOM-1972** first because it contains the intentionally detectable conflict between the approved **Clarity+Forge normal/critical worker topology** and a superseded statement about **one global active Claude session/two total workers**. The investigator and *blind* challenger should each independently find and cite that conflict. The evaluator should not report D6/D8 clean without resolving authoritative sources.

Next, run HOM-1945 (security threat model, D5/D10) and HOM-1943 (nonbehavioral architecture/reuse research, D1/D6/D8). Compare with the original manual M0 baseline using the exact same source revisions, signed-off policy and evaluator version. Capture blockers caught, false positives, unsupported inventions, AC inflation and model usage; do not claim a gain merely because the model produced more words.

### Before advancing to automated support

- [ ] Run this harness at least once with **real authenticated** Claude sessions, preserve independent run metadata and compare with a human-reviewed gold standard
- [ ] Adopt a local, verified Forge City risk/DoR decision hierarchy; no unchecked assumptions
- [ ] Resolve the HOM-1972 conflict in the source issue **after review**, never silently during a benchmark
- [ ] Verify the model/source output is suitable for private retention and representative model cost
- [ ] Build authenticated Linear snapshot retrieval and a real policy-owned output/publishing adapter separately; the harness must never write live issue data or mark a requirement READY by itself

**The gate is a quality-review pilot, not an autonomous tracker/agent service.** 
