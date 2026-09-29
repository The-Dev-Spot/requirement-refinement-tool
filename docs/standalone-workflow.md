# Standalone workflow walkthrough

Use these commands from a repository checkout after installing `requirements.lock`.
Commands run synchronously. There is no model scheduler or background agent loop.

## 1. Create trusted local state and role keys

```sh
python -m clarity work init
mkdir -p "$HOME/.config/clarity-keys"
chmod 700 "$HOME/.config/clarity-keys"
python -m clarity work provision author-agent author --output "$HOME/.config/clarity-keys/author.key"
python -m clarity work provision independent-reviewer reviewer --output "$HOME/.config/clarity-keys/reviewer.key"
python -m clarity work provision owner operator --output "$HOME/.config/clarity-keys/operator.key"
```

The default state directory is `~/.local/state/clarity`; choose another with
`work --state /absolute/private/directory`. Use an owner-only path without symlinked
ancestors. Existing state is never overwritten by init. Key files are written
exclusively with mode 0600; their values are not printed. Record credential IDs
for later revocation. Provisioning is local OS-owner administration, not an API
for an untrusted agent.

**Do not hand an unrestricted agent shell access to the controller's account.**
The commands below demonstrate the API boundary on one machine. For real agent
isolation the operator must control state, code and keys from a separate trusted
execution context. Creating three keys does not by itself sandbox three processes
that all run as the same OS user.

## 2. Prepare a source snapshot

A supplied behavioral requirement uses Gherkin with Feature/Scenario structure.
A non-behavioral requirement uses items in this form:

```text
- [ ] A concrete outcome | Verify: the test, artifact or evidence that demonstrates it
```

Import selected local files with explicit source identity/date and kind:

```sh
python -m clarity import-markdown brief.md acceptance.md --project DEMO --source-id SOURCE-1 --source-date 2026-09-29 --kind checklist --output requirement.json
```

Inspect and complete that JSON: identify interface or regulated applicability,
record actual investigation, add other evidence, enumerate unresolved questions
and proposals, and select the applicable risk/step catalog. The import does not
perform a real investigation or know whether the source is authoritative.

`examples/checklist-requirement.json` is a complete **synthetic demonstration**.
Never copy its all-clear assumptions into customer work. Neutral local imports
use hashes of the selected source and AC files as their source revision.

## 3. Submit and inspect a run

```sh
python -m clarity work --token-file "$HOME/.config/clarity-keys/author.key" create RUN-demo examples/checklist-requirement.json
python -m clarity work --token-file "$HOME/.config/clarity-keys/author.key" status RUN-demo
python -m clarity work --token-file "$HOME/.config/clarity-keys/author.key" list
```

A run has a stable ID, current revision and optimistic `version`. Use the returned
version for every change. Stale operations fail instead of overwriting another
review or answer. An active run for the same source/project redirects work to
resume rather than creating a duplicate. Historical revisions never change.

## 4. Independent review

The independent reviewer reads the entire current snapshot and prepares JSON
with `revision_digest` copied from `status`, plus exactly D1-D10 under `dimensions`.
Every dimension needs `status`, a substantive `rationale`, and `evidence_ids`
referencing the snapshot's evidence, `source`, or `requirement`.

A single dimension record looks like this; it is not a completed assessment:

```json
{
  "status": "NOT_RUN",
  "rationale": "The reviewer has not yet assessed this dimension.",
  "evidence_ids": ["requirement"]
}
```

Save all ten assessments in `review.json`, then:

```sh
python -m clarity work --token-file "$HOME/.config/clarity-keys/reviewer.key" review RUN-demo 1 review.json
```

Replace `1` with the current run version. The runtime ignores no missing checks:
review input cannot supply L1-L8 or force READY. It executes those rules itself,
combines them with the semantic judgments, and persists the result. It verifies
source-ID references but cannot prove the truth or authority of their content.

## 5. Resolve owner questions and revise

Every question has an immutable ID/text. An operator answers a known question
using a selected text file and the current version:

```sh
python -m clarity work --token-file "$HOME/.config/clarity-keys/operator.key" answer RUN-demo 3 Q-1 owner-answer.txt
```

The answer does not automatically edit the requirement. Incorporate it into a new
snapshot, move its ID from open `questions` into `acknowledged_answers`, then:

```sh
python -m clarity work --token-file "$HOME/.config/clarity-keys/author.key" revise RUN-demo 4 revised-requirement.json
```

Obtain another independent review with the new digest/version. A changed owner
answer requires another revision even if the same question ID was previously
acknowledged. Unconfirmed proposals, missing/conflicting evidence and visible
open-question markers still block readiness.

After three rewrites, an operator may authorize `decide RUN-demo <version>
new_rewrite_cycle --reason "..."`. Quarantine release and rejection use the same
command with `release_quarantine` or `reject`. Release requires a clean revised
snapshot, a reason and a fresh independent review; an author cannot self-release.

## 6. Inspect, approve and seal locally

```sh
python -m clarity work --token-file "$HOME/.config/clarity-keys/operator.key" plan RUN-demo
python -m clarity work --token-file "$HOME/.config/clarity-keys/operator.key" view RUN-demo --output RUN-demo.review.html
```

The workbench is a static, read-only snapshot with escaped source content, a diff,
evidence, questions, assessments, the exact plan and audit trail. It has no network
assets, scripts or approval forms. Keep the generated file private and refresh
it after changes. The terminal `plan` is the authoritative current preview.

Use the returned version and digest, not guessed values:

```sh
python -m clarity work --token-file "$HOME/.config/clarity-keys/operator.key" approve RUN-demo <current-version> <displayed-plan-digest>
python -m clarity work --token-file "$HOME/.config/clarity-keys/operator.key" seal <returned-approval-id>
python -m clarity work --token-file "$HOME/.config/clarity-keys/operator.key" export <returned-export-id> --output approved-requirement.json
```

`approve` has a maximum 900-second TTL. `seal` atomically consumes it and stores
the export in the database. Concurrent/repeated seal requests return the same
stored export. A failed output-file write can be retried with a different unused
filename; it does not repeat approval or create another artifact. Outputs are
never overwritten. The export includes source, current draft, revision history,
reviews, owner decisions, exact plan and the audit events preceding sealing.

This action is **not a tracker write**. Source revision means the approved imported
snapshot, not a guarantee that a remote source has remained unchanged since then.
No third-party publisher, remote exactly-once guarantee or downstream dispatch
is implemented.

## 7. Verify, back up and restore

```sh
python -m clarity work --token-file "$HOME/.config/clarity-keys/operator.key" verify RUN-demo
python -m clarity work --token-file "$HOME/.config/clarity-keys/operator.key" backup --output workspace.backup.json
```

Retain the printed backup digest separately. The backup includes private run data
but no capability secret or authentication hash. Protect/encrypt it using your
normal backup system. This release does not encrypt backups itself.

Restore to a destination that does not exist:

```sh
python -m clarity work --state "$HOME/.local/state/clarity-restored" restore workspace.backup.json --digest <separately-retained-backup-digest>
```

Provision fresh keys there. Restored old keys cannot authenticate; all unused
approvals are revoked and previously approved runs return to awaiting approval.
Committed exports and evidence remain available. Restore is tested, but automatic
pruning is still disabled. The backup/JSON import size limit is 20 MB in v0.2.

To revoke a key use `work --token-file <operator-key-file> revoke <credential-id>`.
Revoking an approval's issuing credential invalidates its unused approvals.
The active administrative credential cannot revoke itself.
