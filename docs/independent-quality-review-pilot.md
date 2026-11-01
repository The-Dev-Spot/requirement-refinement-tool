# Running Clarity's independent quality-review pilot

**Status:** local experimental read-only runner. The deterministic L1–L10 checker and Clarity→Forge handoff are merged and CI-tested. The **three-session semantic pipeline** in `scripts/quality_review.py` runs only when explicitly invoked on a machine with an authenticated, recent Claude Code CLI. It has no Jira, Linear, Forge, production, Docker or GitHub write capability. It does not automatically declare READY.

## Portable model selection and review integrity

Clarity now uses a single **repository-owned D1–D10 rubric** and structured
investigator/evaluator/blind-challenger schema. All stages receive the same
pinned dimension definitions from `rubric/definition-of-ready.md`; each
review records a rubric SHA256 and the exact prompt digest, plus requested
and provider-reported model IDs and per-stage process/session receipts.

The quality and acceptance thresholds are **model-independent**: no
incomplete D1–D10, unresolved material finding, unchecked rubric revision,
unknown model, duplicated session or source/policy mismatch can produce a
reviewable candidate. This is a reproducibility **contract**, not proof
that two models have equal semantic accuracy. Actual candidate quality is
measured against independently approved gold cases.

- `--provider claude --model claude-opus-5-5` uses the unmodified Claude Code
  CLI. The runner clears inherited Claude Code parent-session environment
  fields, asks for a concrete model, and checks that the CLI's returned model
  (or a single-model `modelUsage` entry) matches. If no resolved model ID is
  returned, the result is **BLOCKED / MODEL NOT VERIFIED**, never silently
  called Opus just because the surrounding chat was Opus.
- `--provider adapter --adapter-script /trusted/review_adapter.py --model gpt-6`
  uses an **operator-selected**, absolute Python adapter script. It can call
  OpenAI, another approved hosted API, or a local model. Neither n8n issue
  content nor model output may choose the adapter path, model permissions or
  credentials. Adapter configuration is private and executed outside Clarity.
  A new model needs an actual provider adapter and authorized credentials;
  installing Clarity alone does not grant model access.

**Adapter stdin protocol** (one JSON object):

```json
{
  "protocol_version": 1,
  "stage": "evaluator",
  "model_requested": "gpt-6",
  "prompt": "<entire authoritative instructions + rubric + story>",
  "output_schema": {"type": "object"}
}
```

The `output_schema` shown here is abbreviated; the real object is
`quality_review.OUTPUT_SCHEMA`. Adapter writes **one JSON object** to stdout:

```json
{
  "is_error": false,
  "structured_output": {
    "stage": "evaluator",
    "verdict": "PASS",
    "dimensions": [],
    "findings": [],
    "questions": [],
    "summary": "<real evidenced result>"
  },
  "model": "gpt-6",
  "session_id": "<unique provider-generated session ID>",
  "usage": {}
}
```

The illustrative `dimensions: []` above is **not a valid actual evaluator**
result: it must contain *all ten* evidenced D1–D10 records. Likewise,
investigator/challenger dimensions must be empty. The adapter must return the
real resolved model ID and an independently generated session identifier,
not simply echo an arbitrary requested model or a parent chat ID.

Adapter access is a powerful trusted-host capability. The CLI calls the
configured Python program with argv arguments **containing no prompts or
issue text**, passing the full request through stdin and disabling inherited
Claude session flags. The adapter itself is responsible for safe network
configuration, encrypted secrets, provider quotas, output size and honest
model/session provenance; a trusted Forge City supervisor must eventually
authenticate the provider's claims. Do not run an adapter supplied in a ticket.

**Repeat pilot requirement:** Node.js **24+** is enforced by the CLI before
running mechanical L1–L10, and `--model` must be explicitly set for live
reviews. CI tests use synthetic responses and never call paid models.

## 2026-11-01 Opus 5.5 pilot: stage schema and hosted runner correction

The [HOM-1972 rerun](../docs/m0-cross-model-acceptance-benchmark.md)
exposed an important distinction: Opus 5.5 was explicitly requested, but
the nested hosted Claude Code CLI returned `model: null` and used both
`claude-opus-5-5` and an auxiliary `claude-haiku-5-5` in `modelUsage`.
Token share cannot prove which model generated the stage result. The same
session ID as the hosting Claude conversation was reused, despite earlier
environment cleanup. **This is NOT valid multi-session model provenance.**

Clarity now passes **stage-specific structured-output schemas** to both
Claude CLI and provider adapters. Investigator and challenger require
`dimensions: []` (`maxItems: 0`); evaluator requires exactly 10. The
independent host validator continues rejecting violations. A provider
stage that returns malformed data now produces a **private, mode-0600 BLOCKED
report** with failure code, SHA-256 and bounded **raw provider envelope**,
instead of silently dropping the evidence. The raw output may contain private
issue content; keep reports outside the public repository and apply your
normal retention controls. Never upload raw receipts to public CI artifacts.

**Hosted Claude sessions are not standalone review workers.** Clarity detects
known hosted session/ingress markers and returns
`HOSTED_SESSION_NOT_ISOLATED` before spending inference. On a separately
authenticated operator-controlled host (e.g. R720-AI or a workstation),
run the unmodified Claude CLI with its own legitimate login and explicitly
specified model. A hosted claude.ai parent conversation, a model name in
an n8n event, or `modelUsage` with multiple model IDs is insufficient to
prove three independent reviewer sessions.

When CLI output lacks an authoritative top-level resolved model and lists
multiple models, the result **remains BLOCKED**. Do not infer the main
model from output-token counts, and do not fabricate `model_verified`.
For providers whose native CLI cannot report verifiable model/session data,
use a trusted operator-owned API adapter that records the actual provider
model and request identity via supported provider response fields.
That adapter and its attestation still require qualification: an arbitrary
adapter echoing the requested model is not trustworthy.

Repeat HOM-1972 only from a properly authenticated, independent host with
Node.js 24+, version-locked sources, the exact policy and the fixed Clarity
runner. Do not rerun nested inside a hosted conversation simply to get
another BLOCKED result.

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

## Explicit draft-policy benchmark

For first M0 research, a project risk overlay may still be **DRAFT** and the
generic DoR may not yet be ratified. The default runner prevents model
invocations in that state. To **deliberately test** model finding quality
without granting readiness, pass:

```sh
python3 scripts/quality_review.py \
  --input /private/forge-city/HOM-1972.snapshot.json \
  --policy /private/forge-city/project-policy-draft.json \
  --output /private/forge-city/HOM-1972.draft-pilot.json \
  --provider claude --model claude-opus-5-5 --pilot-with-draft-policy
```

Use `adopted: false`, `risk_register_status: DRAFT`, and the source-
versioned proposed decisions (never counterfeit an APPROVED policy). This
permits separate *read-only* model calls for testing their critical reasoning
but the final report stays **BLOCKED** and cannot authorize writes or Forge
work. All program safety settings and usage controls still apply. The
`pilot_with_draft_policy` field records that the override was explicitly
requested; CI only validates synthetic fixtures. **Never use this flag as a
production readiness bypass.**

The report contains input/policy hashes, actual preflight result, invocation IDs and model-provided output/metadata, plus a machine-derived aggregate. It does **not** attest that input policy was approved by a cryptographically verified owner or that model findings were factually correct. These require a trusted supervisor and human adoption before advancing to automatic Forge City dispatch.

## Evidence-first context from Linear and GitHub (HOM-1989, experimental)

Clarity can now **consume a pre-collected read-only, source-pinned context
packet** using `--evidence-pack /private/context.json`. This is **not a
GitHub/Linear API client**: credentials and API calls belong to a future
independent, allowlisted coordinator, NOT the isolated model reviewer.
The optional input preserves backward compatibility with legacy reviews.

Evidence packet v1 is a JSON object with *exact* keys:
`schema_version: 1`, `kind: "clarity-context-evidence"`,
`target_issue` (e.g. HOM-1972), `story_sha256`, `policy_sha256`,
`review_scope`, `freshness: "SOURCE_UNVERIFIED" | "SOURCE_CHANGED"`,
and `sources` (1..30 entries). Digests of the story/policy are hashes of
canonical JSON (sorted keys, compact separators, ASCII escaped). Each source
has: `id` (S-001), `provider` (linear/github), `url`, `revision`,
`scope`, `source_kind` (ISSUE/DECISION/DOCUMENT/CODE/TEST),
`authority_claim` (UNVERIFIED/CLAIMED_ACTIVE/DRAFT/HISTORICAL/IMPLEMENTATION),
`excerpt` and its `excerpt_sha256`. Source quotes are limited to 3200
characters each. GitHub evidence requires an **exact 40-char commit SHA** in
both its revision and `/blob/{commit}/path` URL. Linear evidence requires a
specific issue/document URL and source revision claim.

`authority_claim` is deliberately a **claim**, never verified governance.
GitHub code or tests may show implemented behavior but may **not** ratify
requirements; a newer Linear comment is not automatic owner approval.
Original pilot and future target can use different `scope` values. All three
independent reviewer prompts include the same packet as **untrusted source
data**, with instructions to cite relevant source IDs and avoid re-asking
answered questions. The cold challenger still receives *no investigator or
evaluator output*.

**Fail closed:** this v1 packet has no cryptographically authenticated
current-tracker/owner issuer. `CURRENT_VERIFIED` is not an allowed value.
Even a model review that seems clean remains `BLOCKED` for external-source
freshness/authority, and any `SOURCE_CHANGED` packet records a separate
staleness reason. The existing draft DoR/risk register and any open questions
still block independently. No tracker writes, network access, Slack sending,
auto acceptance or Forge dispatch are added. Do **not** reuse the original
2026-11-01 historical pilot SHAs for the normalized HOM-1972 story.

A trusted collector is still needed to retrieve a versioned current Linear
issue/project/decision snapshot plus GitHub allowlisted files at fixed commit
SHA, bind the exact owner-adopted policy and verify freshness, then deliver
this private packet. A later trusted acceptance issuer is separately
responsible for any `ACCEPTED_FOR_FORGE` status. The first synthetic tests
verify safe citations, stale/bad digest rejection and no unearned PASS.

Tracking: [HOM-1989](https://linear.app/sashafelix-homelab/issue/HOM-1989).

## Offline question proposal outbox (HOM-1986, initial delivery)

Clarity can now **extract** questions from an already-completed local
independent-review report, without making Slack/network/connector calls.
The reviewer remains isolated and has **no** issue writer, Slack token,
acceptance issuer, or Forge dispatch authority. Do not run this inside
an untrusted PR job with sensitive source.

From an operator-owned Python environment with access to the same
Clarity scripts and a mode-0600 private review report:

```sh
python3 scripts/export_review_questions.py \
  --report /private/reports/<run>.review.json \
  --private-output /private/questions/<run>.proposals.json \
  --outbox-output /private/outbox/<run>.notification.json
```

This command writes **two exclusive mode-0600 JSON files**:

- Private proposals: source/policy/rubric review SHA, report SHA, stable
  batch/question IDs, each original proposed question and list of stages
  asking it, and explicit `authority: UNVERIFIED`. Only an authenticated,
  role-bound coordinator may present them to a user or modify a tracker.
- Sanitized notification event: deterministic event ID, SHA-backed batch
  identity, count, review status and permission flags. **No questions,
  findings, prompts, raw model output, credentials, session ID or private
  path** are copied into the outbox. A separate trusted service may eventually
  consume this event and send a deduplicated Slack notification with a link
  to authenticated question collection. No such service is included here.

Stage question proposals require the stage's real Clarity result plus
matching locally verified model/session metadata. Invalid, malformed,
group-readable or symlinked reports fail closed. The exporter does **not**
cryptographically attest provider identity or original tracker authority:
`reviewed_input_sha256` is the **review packet digest**, not an
independently fetched canonical Linear/Jira issue revision. Only the
trusted Forge City gateway can bind it to an authenticated source.

If no questions were emitted but quality remains BLOCKED, the outbox
marks `REVIEW_BLOCKED_WITHOUT_QUESTIONS`, not success. The outbox is a
*proposal*, never `ACCEPTED_FOR_FORGE`; notifications and human answers
must not auto-approve or release work to Forge. Retries must deduplicate by
event ID; the CLI deliberately never overwrites an existing report/event.
Use new per-run output paths and the coordinator's durable event ledger
when wiring the service.

Design: [HOM-1986](https://linear.app/sashafelix-homelab/issue/HOM-1986).
Slack endpoint, authenticated owner answers, source compare-and-swap,
worker queue and re-review are **not yet implemented** in Clarity.

## Opt-in scoped decision provenance (HOM-1985)

A reviewed source can contain **pilot-only**, **target-system**, and
**historical** decisions that differ without necessarily conflicting.
Reviewers must still reject truly contradictory current decisions in the
**same** scope. Source text, not a model inference or a newer timestamp,
establishes explicit supersession and project authority.

For a **new** scoped review, set the exact matching `review_scope` in both
the frozen story JSON and operator-selected policy JSON. Add the policy's
`decision_register` array with **exact** keys: `id`, `scope`, `status`,
`source`, `revision`, `authority`, `text`, and `supersedes` (array of
decision IDs). Statuses are `ACTIVE`, `HISTORICAL`, or `PENDING`. Move
all old `decisions` records into the scope-aware register and use
`"decisions": []` to avoid mixing unlabeled precedent into the reviewed
current authority.

Example (abbreviated **synthetic** project policy; no owner attestation):

```json
{
  "project": "Synthetic Forge City",
  "adopted": false,
  "risk_register_status": "DRAFT",
  "review_scope": "PILOT_RC",
  "decisions": [],
  "decision_register": [
    {"id": "OLD", "scope": "PILOT_RC", "status": "HISTORICAL",
     "source": "archived issue", "revision": "r1", "authority": "owner-claim",
     "text": "Old pilot limit", "supersedes": []},
    {"id": "CURRENT", "scope": "PILOT_RC", "status": "ACTIVE",
     "source": "new issue", "revision": "r2", "authority": "owner-claim",
     "text": "One operator-authorized pilot", "supersedes": ["OLD"]},
    {"id": "AUTOMATION", "scope": "TARGET_AUTO", "status": "ACTIVE",
     "source": "target issue", "revision": "r3", "authority": "owner-claim",
     "text": "No per-issue Start on a qualified automatic service", "supersedes": []}
  ]
}
```

The story JSON also needs `"review_scope": "PILOT_RC"`. This opt-in
contract validates scope equality, unique IDs, allowed statuses, at
least one active decision in the selected scope, and explicit
**same-scope** supersession of records marked historical. A claimed
supersession of an active or different-scope decision is rejected before
model inference. Any `PENDING` decision in the chosen scope **blocks a
reviewable candidate**, even if the model reports all PASS. Legacy
unscoped packets still work through the preexisting rules.

This is **structural validation only**. Clarity cannot verify that an
`authority` field came from the owner, authenticate the source revision,
or mechanically detect semantic contradictions between two active
decisions. All three independent stages receive explicit scoped
provenance instructions and must flag real same-scope contradictions;
a separate authenticated issuer must verify actual precedence,
adoption, source freshness and signing. **Neither a decision register
nor a green score confers publication or Forge execution authority.**

See the Forge City canonical decision register in Linear and
[HOM-1985](https://linear.app/sashafelix-homelab/issue/HOM-1985).

## First M0 pilot

The **frozen 2026-11-01 HOM-1972 source** intentionally contained
contradictory, unlabeled manual pilot and automatic target text; preserve
its original SHA and three-stage BLOCKED result for the regression
baseline. The current Linear HOM-1972 was normalized afterward into
PILOT_RC and explicitly delegates worker capacity and automatic
dispatch to HOM-1973/HOM-1979. It is a **different source revision**.
For the next review, retrieve and freeze both the updated tracker
description and the current scoped project-policy packet, and verify
their revision/hashes before running the model. Do **not** reuse the old
pilot result or silently rewrite the historical findings.

Next, run HOM-1945 (security threat model, D5/D10) and HOM-1943 (nonbehavioral architecture/reuse research, D1/D6/D8). Compare with the original manual M0 baseline using the exact same source revisions, signed-off policy and evaluator version. Capture blockers caught, false positives, unsupported inventions, AC inflation and model usage; do not claim a gain merely because the model produced more words.

### Before advancing to automated support

- [ ] Run this harness at least once with **real authenticated** Claude sessions, preserve independent run metadata and compare with a human-reviewed gold standard
- [ ] Adopt a local, verified Forge City risk/DoR decision hierarchy; no unchecked assumptions
- [ ] Resolve the HOM-1972 conflict in the source issue **after review**, never silently during a benchmark
- [ ] Verify the model/source output is suitable for private retention and representative model cost
- [ ] Build authenticated Linear snapshot retrieval and a real policy-owned output/publishing adapter separately; the harness must never write live issue data or mark a requirement READY by itself

**The gate is a quality-review pilot, not an autonomous tracker/agent service.** 
