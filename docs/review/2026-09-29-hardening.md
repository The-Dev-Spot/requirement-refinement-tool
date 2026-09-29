# Standalone workflow hardening — 29 September 2026

## Scope

Built on the merged personal baseline, preserving the ten reasoning roles while
making the local workflow enforceable and resumable. The owner explicitly chose
a standalone product; no development-pipeline integration is included.

## Delivered controls

| Original gap | Implemented change |
| --- | --- |
| Prompt-only lifecycle | SQLite run state, immutable revisions, optimistic versions, restart/resume |
| Model-supplied approval records | Operator-provisioned role keys, authenticated actions, fixed actor roles and author ownership |
| Missing executable checks | Official Gherkin parser/compiler plus L1-L8 machine rules and structured checklist verification |
| Rewriter judging its own output | Separate reviewer capability and snapshot-bound semantic assessments with evidence references |
| Stale or reusable approval | Exact plan/policy/source/review hashes, expiry, credential revocation and atomic single consumption |
| Duplicate action on retry | Transactionally stored local export, stable replay response and separate retryable file retrieval |
| Lost owner decisions | Stable question IDs, authenticated answers, mandatory incorporation in a new revision and re-review |
| Silent unlimited iteration | Three-rewrite ceiling and explicit operator-authorized new cycle |
| Weak recovery evidence | Structured self-contained exports, integrity verification and explicit tested backup/restore |
| Embedded untrusted instructions | Bounded heuristic detection, sticky quarantine and operator-only release after a clean revision |
| Missing operator visibility | Escaped offline workbench with diff, evidence, questions, checks, exact plan and audit records |
| Tracker-specific coupling | Neutral snapshot contracts, explicit local Markdown import and optional read-only scoped Linear reader |

## Validation scope

The suite exercises baseline helpers plus role separation, malformed inputs,
stale reviews and plans, policy changes, replay, concurrent writes, transaction
rollback, immutable records, question loss, changed owner answers, quarantine,
revocation, backups, restoration, HTML escaping, CLI error handling, source
imports and mocked tracker pagination/errors. CI installs the hash-pinned official
parser and runs its grammar/compiler tests on Python 3.11 and 3.13.

Local test environments without package-download access skip official-parser tests;
that is not a parser pass. CI must pass those tests before merge. The synthetic
rule benchmark contains 13 labelled cases and explicitly does not measure model
accuracy. Final run counts and the exact tested commit are reported in the PR.

## Known limits retained deliberately

This is an authenticated local controller, not enterprise sign-in, a hosted app
or a filesystem sandbox. Its OS owner can change code/state; isolate untrusted
agents from controller state and keys. Capability identities do not prove genuine
model independence. The controller persists submissions and review decisions but
does not automatically call the ten agents or verify their private reasoning.

Syntax/lexical checks and known-pattern injection detection are not semantic truth
verification or universal security guarantees. Live Linear integration and native
agent-host behavior have not been exercised with real credentials in this session.
The static workbench is read-only. No tracker mutations, remote publication,
automatic deletion, backup encryption or pipeline handoff were implemented.
