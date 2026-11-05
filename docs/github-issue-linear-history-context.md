# GitHub-only intake, optional Linear historical evidence

**Canonical actionable source: GitHub Issues only.** Clarity may inspect Linear
history for prior work and decisions, but Linear issues are never new
development/review targets and cannot trigger Forge.

## Existing runtime versus this first slice

- Existing R720 GitHub collector continues to read GitHub Issues, source
  files and comments only. It has no Linear credentials.
- This PR introduces scripts/collect_linear_history.py, a **separate,
  operator-invoked, read-only historical reader**. It does not install a
  container, grant permissions, search arbitrary Linear projects, execute
  models, automatically resolve questions or change the Inbox. Deployment
  and project-specific selection remain **future milestones**.
- The v1 historical source reader reuses the fixed Linear GraphQL **read**
  query and private credential-file protections from the older archive
  collector. The optional [v2 detailed reader](linear-history-status-comments.md)
  adds scoped metadata preflight, workflow status and bounded comments.
  Both read only exact IDs from the owner-scoped plan.
  Current issue intake remains a canonical owner/repo#number
  GitHub ID, checked against the current story and policy repository
  allowlist.
- The reader writes a private immutable, mode 0600 packet; its status
  is SOURCE_UNVERIFIED or SOURCE_CHANGED, authority is
  HISTORICAL_UNVERIFIED, and *all* approval/dispatch/intake flags are
  false. Historical evidence is **not** a claim of current adoption.

## Proposed private input shape

The operator must explicitly select relevant historical Linear issues.
There is no organization-wide search, automatic import, or sync.

~~~json
{
  "schema_version": 1,
  "target_issue": "example-org/sample-repo#123",
  "review_scope": "APP_REVIEW",
  "workspace": "example-workspace",
  "allowed_issue_prefixes": ["HIST"],
  "historical_issues": [
    {"id": "HIST-101", "scope": "APP_REVIEW", "focus": "prior decision"}
  ]
}
~~~

These are placeholders. Do not assume the historical record exists, is
relevant, is approved or is the latest decision. The target issue must
already exist in GitHub; the plan is never a way of creating it.

When separately deployed, the tool's CLI is:

~~~text
python3 scripts/collect_linear_history.py \
  --plan /private/history-plan.json \
  --story /private/github-story.json \
  --policy /private/github-policy.json \
  --linear-key-file /private/secrets/linear-history-read.key \
  --output /private/history/history-unique-run.json
~~~

**Do not run this in the existing GitHub collector or Claude reviewer
containers.** The historical reader needs its own strictly read-only token,
scoped to permitted projects, private mounts, network allowlist and
deployment review. No Linear secret should be added to the GitHub collector.

## Future Question Relevance Gate

Once an independently verified, bounded historical packet exists,
the gate should compare it with the current GitHub issue, pinned
repository implementation, ADRs, PRs and the independent reviewer stages' candidate
questions for whichever canonical GitHub issue is under review.

A candidate disposition must retain question ID, reviewers, source IDs,
source timestamps and exact review/input digests:

- RESOLVED_BY_EVIDENCE: source and applicability are checked; **not**
  inferred from a keyword match or solely an old Linear decision.
- NEEDS_FRESH_TECHNICAL_VERIFICATION: relevant answer may exist but
  requires a fresh GitHub/host check.
- NEEDS_OWNER_DECISION: material policy/architecture/business decision
  still lacks current authorized evidence.
- DUPLICATE_OF: same underlying question; original independent stage
  provenance is retained.

No category alone approves, edits, dispatches or deletes questions.
Require an independent acceptance issuer to verify approval and current
GitHub revision before any Forge work order. No automatic suppression is
implemented in this initial history-reader PR.

## Limitations

The legacy v1 query retrieves identifier, title, description and updatedAt,
and retains unverified project mapping. The optional v2 reader checks actual
workspace/team/project IDs and includes current workflow status and bounded
comment excerpts. It does not fetch a status-transition audit log or certify
project policy, owner authority, deployment or semantic answers. All historical
packets remain SOURCE_UNVERIFIED; live integration has not been exercised.
