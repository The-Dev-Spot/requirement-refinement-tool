# Current GitHub source freshness — read-only collector check

The earlier Clarity researcher and independent challenger operate on
a **pinned snapshot**. This separate GitHub-only checker establishes
whether the GitHub Issue and referenced source snippets still match
GitHub's current read API **at the time of checking**.

This is NOT a replacement for the reviewer/acceptance gate.

## What it checks

- Revalidates the original GitHub-only v2 evidence against the exact
  story/policy scope and repository allowlist before reading credentials.
- Uses only a restricted **GitHub read** credential in a collector context.
- For each GitHub Issue source, re-reads the complete issue discussion
  (bounded comments) and checks `updated_at` and whether the pinned
  source excerpt is still present.
- For each code/test/document source, reads the file at its original
  SHA-pinned revision, confirms the original snippet still exists,
  reads the repository's actual default branch and checks that HEAD
  is still the pinned commit. A moved branch is reported as changed,
  even when the old pinned file remains available.
- Rechecks issue contents and default-branch HEAD once again after the
  initial pass to detect changes during the verification window.

It writes an immutable, private, mode-0600 JSON receipt with per-source
statuses, the original evidence hash and one of:

- `MATCHED_AT_READ_TIME` — observed GitHub data matched the snapshot.
- `SOURCE_CHANGED` — a cited issue revision, branch HEAD, or quoted
  content no longer matches.

An unavailable API, missing credential, oversized comment discussion or
unexpected metadata is an error and **fails closed**.

## Boundaries

This tool does **not** declare business policy approved, resolve semantic
questions, suppress questions, import answers into the Inbox, mutate a
GitHub issue, access Linear, or authorize Forge. It never sends GitHub
tokens or raw source content to a model.

The tool is intended for a separately reviewed read-only GitHub collector
environment. It must not be run inside the Claude reviewer/researcher
container, which should have **no GitHub credential or API access**.

Future trusted reconciliation will need to bind this receipt to the exact
research/challenger artifacts and recheck again before issuing acceptance.
If a current issue or branch changed, the right result is **recollect
and re-review**, not to assume an old decision still applies.

## Example (not yet deployed)

~~~bash
python3 scripts/recheck_github_sources.py \
  --story /private/inputs/story.json \
  --policy /private/inputs/policy.json \
  --github-evidence /private/inputs/github-evidence.json \
  --github-key-file /private/secrets/github-read.key \
  --output /private/reports/source-recheck-unique.json
~~~

No real API request is executed in CI; all tests use synthetic GitHub
response objects. The code is not yet installed on any R720 server.
