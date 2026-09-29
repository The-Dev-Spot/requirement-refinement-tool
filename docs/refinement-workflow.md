# Standalone brief-to-Gherkin walkthrough

Run commands from a repository checkout, using Python 3.11+ on POSIX. Keep the
controller account, state and keys outside an untrusted agent workspace.

## Initialize and provision

```sh
python -m pip install --require-hashes --only-binary=:all: -r requirements.lock
STATE="$HOME/.local/state/clarity"
KEYS="$HOME/.config/clarity-keys"
mkdir -p -m 700 "$KEYS"
python -m clarity.refine --state "$STATE" init
python -m clarity.refine --state "$STATE" key --actor author --role author --output "$KEYS/author.key"
python -m clarity.refine --state "$STATE" key --actor independent-reviewer --role reviewer --output "$KEYS/reviewer.key"
python -m clarity.refine --state "$STATE" key --actor requirement-owner --role operator --output "$KEYS/operator.key"
python -m clarity.refine --state "$STATE" serve
```

Provisioning is OS-owner administration, never an agent or HTTP action. Output
files are exclusive and owner-only; secrets are not printed. An actor cannot take
both author and reviewer roles. Separate key names alone do not establish genuine
independent human/model review; provision the appropriate trusted reviewers.

`init` creates the core workspace only if it does not already exist, then performs
an additive transactional migration of four refinement tables. It does not replace
existing v0.2 runs. Unknown or partial schema versions are rejected. Take an explicit
backup before upgrading a workspace containing valuable records.

## Use the workbench

Open the printed loopback address and sign in with an appropriate capability key.
The browser stores an opaque session ID, not the capability. Sign-in rotates the
session; sessions expire after one hour. No key is placed in a URL. Do not expose
this listener through a tunnel or public reverse proxy.

An **author** can capture an ordinary-language request, add selected reference
excerpts, ask decision-focused questions and submit a draft. The request need not
already contain professional analysis or acceptance criteria. Guided versus concise
presentation does not change the quality standard.

An **operator** confirms whether references have authority and apply to this need,
answers business questions, records explicit duplicate/scope resolutions and later
approves the exact handoff. A requester lacking authority is helped to obtain the
correct decision, not encouraged to invent it. Changing an answer retires its old
decision source and forces a new revision/review.

A **reviewer** independently assesses the final statements and scenarios. Review
includes a cold-read test, applicability of failure/boundary coverage and a challenge
to find materially different interpretations. Syntax results come from the controller,
not reviewer JSON. Hard failures and unresolved decisions cannot be waived.

The operator then inspects the proposed handoff, chooses a local export profile,
approves the exact plan and seals it. Download is a separate, read-only operation.
The full ZIP contains private evidence; import only its `.feature` file into test
management after validating the chosen Xray instance's settings.

## Optional bounded model assistance

Model use is off by default. With an operator-managed Ollama instance on loopback,
choose actual installed models explicitly:

```sh
python -m clarity.refine --state "$STATE" serve \
  --model YOUR_LOCAL_AUTHOR_MODEL \
  --review-model YOUR_LOCAL_REVIEW_MODEL
```

The author action investigates selected evidence and either proposes targeted
questions or submits a strict draft. Questions are stored atomically and the UI
shows the next highest-impact decision. Existing unanswered questions stop further
drafting calls instead of being repeatedly asked or silently guessed.

The reviewer action uses a fresh prompt without the writer's self-score or an
older review's verdict. Each response must match its contract. Model results
cannot approve anything, alter policy, issue tools, or write to a tracker.

Calls are synchronous with bounded transport/input/output settings and a persistent
attempt budget (six by default). Attempts are reserved before inference; failed or
interrupted calls remain visible and are not automatically retried. Rewrites have
a separate three-rewrite ceiling. Only an operator can authorize another cycle.
The controller records model name and elapsed time, not private reasoning traces.

A loopback URL does not guarantee that the backend performs local inference. Verify
model deployment and data handling, including whether a chosen model is cloud-backed.
The transport follows no redirects, uses no ambient HTTP proxies and has no arbitrary
URL option. The current implementation has transport/contract tests, not live-model
quality certification. No API key or model has been assumed on your behalf.

Official transport reference: https://docs.ollama.com/api/chat

## CLI and host-driven use

```sh
python -m clarity.refine --state "$STATE" capture \
  --key-file "$KEYS/author.key" --id REQ-demo --project PERSONAL \
  --brief-file /path/to/request.txt
python -m clarity.refine --state "$STATE" status \
  --key-file "$KEYS/author.key" --id REQ-demo
```

`action submit` and `action review` accept a strict JSON file with `--input` and
require the current `--version`. Contracts are in `clarity/refine/contracts.py`;
`examples/refinement-reference.json` is synthetic, not a template of approved facts.
Do not copy its PASS judgments or source authority into real work.

Other explicit actions cover asking/answering, source confirmation, question
resolution, exact approval and new cycles. `plan` shows the bytes and hashes to
be approved. `seal --approval <id> --output <new-path.zip>` seals and writes a local
bundle; retrying with a new output path retrieves the same sealed content. Existing
files are never overwritten. `verify` checks refinement record and export integrity.

Project policy is set with the operator-only `policy --project ... --input ...`
command. Draft submissions cannot include their own risk register or relax the
quality checks. The original `.github/project-config.json` remains the v0.2/editor
configuration; it is not silently treated as the trusted v0.3 policy store.

## Evaluation and boundaries

The parity corpus in `examples/refinement-parity.json` represents one business need
from expert, partial and ordinary-language starting points, with the same supplied
reference policy. It is an initial synthetic corpus awaiting human ratification.
Provide actual final drafts and independent reviews keyed by case ID:

```sh
python -m clarity.refine.benchmark examples/refinement-parity.json /path/to/outputs.json
```

The report separates groups, includes missing outputs as failures and distinguishes
contract results from semantic/model quality. Reusing a reference output only tests
the contract; it is not evidence that a model can derive that output from each brief.
Add human-labelled cases, repeated model trials and blind developer/tester reviews
before claiming equal quality across user groups.

The older snapshot CLI and exports remain available, but new refinement runs are
stored separately and cannot be approved through the older API. The updated v2 backup
envelope explicitly includes the additive tables; after restore, run refinement integrity checks
as well as the legacy checks. Old credentials remain disabled by the existing
restore procedure, so unused refinement approvals cannot be exercised with a new
key. Backup encryption and automated retention are not implemented.
