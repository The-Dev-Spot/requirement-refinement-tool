# Explicit document selection and offline pilot replay

This connects discovered document candidates to the existing GitHub-only
collector and makes the private artifacts replayable without model/provider
calls. It does not close questions, enable Inbox delivery or grant approval.

## Selection and fresh collection

`select_discovery_evidence.py` accepts an explicit list of document candidate
IDs tied to the exact canonical discovery report digest and target issue:

~~~json
{
  "schema_version": 1,
  "kind": "clarity-discovery-document-selection",
  "target_issue": "example-org/project#123",
  "discovery_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "candidate_ids": ["D-001"]
}
~~~

These are fictional format examples. The digest and IDs must come from the
actual discovery report, never be invented. Empty, duplicate, unknown or PR
selections fail; PR candidates are not silently omitted or treated as Issues.

Before reading credentials, the adapter validates the discovery contract,
story/policy/scope/repository/selection hashes, false authority flags, exact
document paths, pinned revisions, excerpt hashes and citation URLs. Selected
paths must remain under the operator's discovery directory prefixes.

In the separately authorized read collector, it verifies that the discovered
default branch and HEAD still match, re-reads each selected file at that commit
and compares full-content hashes. It then invokes the existing collector for
the canonical target Issue with **all bounded comments**, plus selected documents.
The resulting evidence, issue revision, source URLs/excerpts and final default
branch must still match selection. Stale or changed sources block output.

This adapter currently supports `main`/`master` default branches, matching the
existing collection-plan contract. Other branch names need a separate extension.

## Private collection directory

The output directory is newly created, mode 0700, with mode-0600 files:

| File | Contents |
|---|---|
| discovery.json | Original non-authoritative discovery candidates |
| selection.json | Explicit selected IDs and discovery binding |
| collection-plan.json | Reproducible GitHub-only collector plan |
| evidence.json | Fresh v3 source-bound evidence |
| discussion-snapshot.json | Authenticated original issue-discussion snapshot |
| collection-receipt.json | Exact file-byte hashes and completion marker, written last |

No file is overwritten. A write failure may leave a partial private directory;
without the final completion marker it cannot be replayed. Use a new directory
for a retry. The receipt is an integrity manifest, not signed operator approval
or certification of who selected the documents. Selection authority remains
`OPERATOR_SELECTED_UNVERIFIED`. The signed snapshot authenticates the evidence
boundary using the previously defined trusted collector/reconciler secret.

## Offline replay

`run_offline_pilot.py` reads only private files. It checks the completion manifest,
fixed file set, file-byte hashes, reproduced plan, source coverage and authenticated
snapshot. It never executes another script, launches a model, reads a GitHub or
Linear token, calls a provider, refreshes a source, or writes a tracker/Inbox.

Existing review artifacts can be supplied as an uninterrupted prefix:

| Supplied artifacts | Validation |
|---|---|
| None | Collection provenance only; review/model stages remain NOT_RUN |
| review | Rebuild question preview from the exact raw source inputs |
| review + research | Replay original research prompt, batch, quotes and dispositions |
| review + research + challenge | Replay independent prompt, sessions, quotes and outcomes |
| All above + freshness | Authenticate the signed readback and enforce receipt age, then reconcile |

The runner rebuilds the preview rather than trusting a caller-edited preview.
Missing stages remain `NOT_RUN`; missing review means `topic_count: null`, not
zero questions. Gaps, invalid reports, changed inputs, bad signatures or expired
receipts fail validation. The existing freshness limit defaults to 300 seconds,
with trusted configuration limited to 1–900 seconds. There is no CLI clock override.

All successful reports have `status: BLOCKED`. Exit 0 means replay succeeded,
not that requirements are approved. Every topic remains unresolved, including
supported-answer/duplicate candidates. Full replay still requires semantic,
materiality, current owner/policy authority and a protected Inbox adapter.
Model receipts are checked for consistency, not upgraded into proof of model
origin or semantic correctness. Snapshot matching is limited to read time.

Optional Linear history is validated as read-only historical context. It must
be the exact packet used by research/challenge; changing it invalidates replay.
GitHub Issues remain the only actionable intake. All approval, suppression,
Inbox import, policy and Forge authority flags remain false.

## Future authorized commands (not deployed or executed live)

The first command belongs in the separately authorized read collector and makes
GitHub reads. It uses the existing private random attestation secret; no key is
generated or installed by this change:

~~~sh
python3 scripts/select_discovery_evidence.py \
  --discovery /private/discovery.json --selection /private/selected-documents.json \
  --story /private/story.json --policy /private/policy.json \
  --github-key-file /private/secrets/github-read.key \
  --collector-key-file /private/secrets/collector-attestation.key \
  --output-dir /private/pilot-collection-unique
~~~

The replay command belongs in the trusted **offline** reconciler, which must
not hold provider credentials. It validates the collection without running a review:

~~~sh
python3 scripts/run_offline_pilot.py \
  --story /private/story.json --policy /private/policy.json \
  --collection-dir /private/pilot-collection-unique \
  --collector-key-file /private/secrets/collector-attestation.key \
  --output /private/offline-pilot-unique.json
~~~

Add existing `--review`, `--research`, `--challenge`, `--freshness` and optional
`--linear-history` files only when those independently authorized artifacts exist.
Keep the original story/policy bytes used for review; reserializing them changes
their raw hashes and requires a new review. The collector key belongs only in
trusted collectors/reconcilers and must never be exposed to a model runtime.

CI uses synthetic GitHub responses, synthetic keys and mocked model outputs.
No R720-AI access/deployment, paid model use, live collection, credential
provisioning or requirements approval is part of this implementation.
