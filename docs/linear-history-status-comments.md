# Read-only historical Linear status and comments

Clarity can use prior decisions recorded in comments as research context while
GitHub Issues remain the only actionable review/development intake. The v2
historical reader supplements the existing v1 title/description collector;
it does not create an intake path, a writer or a model invocation.

## Explicit scope and provider reads

Each v2 selected issue specifies an expected **team UUID** and **project UUID**.
Explicit `project_id: null` means the operator selected an unassigned issue,
and is accepted only if the API also reports no project. A team prefix alone
is insufficient. Workspace is checked against the API-returned issue URL.

Before requesting descriptions/comments, a fixed metadata-only GraphQL query
checks identifier, workspace, team ID/key and project ID. A second fixed query
gets the description, current workflow state and comments only after that
match. Full results are checked again, including immutable issue identity and
each comment's issue UUID and provider-returned URL. Project/team moves between
the reads block processing.

The reader repeats the metadata/detail pair for each selected issue to detect
changes during collection. It compares a canonical structured digest of the
entire retrieved record, including state and full comment bodies, so edited,
added or deleted comments and status changes are caught even when the issue's
updatedAt is unchanged. No mutation, discovery query, general query text,
cross-project traversal or automatic pagination is available.

## Bounds and provenance

| Item | Contract |
|---|---|
| Selected issues | 1–12 explicit historical IDs |
| Provider requests | At most 4 per selected issue, with existing transport timeout |
| Comments | At most 20 visible comments per issue; request 21 to detect overflow |
| Pagination | Both pageInfo directions must explicitly be false |
| Full discussion | Maximum 90 KB canonical record per issue |
| Comment excerpts | Maximum 800 characters; focus-centered when the selected phrase is present |
| Entire packet | Maximum 90 KB; excess fails rather than dropping sources |
| Thread identity | Parent IDs must exist in the packet, without cycles |
| Authors | Stable user IDs only; null is unknown/integration/deleted identity, never inferred ownership |
| Comment citations | `L-C-<comment-uuid>`, exact provider URL, revision and excerpt hash |

The API query includes archived comments. Visibility is still limited by the
credential's provider permissions. Inline comments without a verifiable issue
association, inaccessible parents, partial GraphQL results, malformed dates,
wrong project mappings and oversized discussions fail closed.

The selected focus phrase must occur in the issue or a comment. A comment-only
decision can therefore be retrieved even when the description is sparse.
Every visible comment within the bounds has an excerpt; truncation is explicit,
and the full body/discussion is represented by hashes. The existing conservative
credential detector checks emitted excerpts and state names. It is not a full
secret scanner or permission system.

## Downstream contract

V2 packets retain the explicit selection manifest and its digest. The relevance
gate revalidates scope, exact selected IDs, team/project metadata, source shapes,
comment/thread identities, citation URLs and excerpt hashes. Individual comment
IDs are available to both research and independent challenge validation. A
comment quote cannot be attributed to its parent issue's excerpt instead.

Both model prompts contain the v2 context and exact canonical history packet
digest. Changes to selected history, state or comments invalidate prior model
receipts during replay. This code does not execute models; existing model stages
still require separate explicit authorization and isolated runtimes.

All output remains `SOURCE_UNVERIFIED` / `HISTORICAL_UNVERIFIED`. The mapping label
`API_IDS_MATCH_OPERATOR_SELECTION` records a data match, not permission or policy
adoption. Workflow “Done” does not prove implementation, tests or deployment.
A comment saying “approved” and its author's ID do not establish current owner
authority. Timestamps alone cannot establish supersession.

Historical comments alone cannot satisfy `ANSWERED_BY_GITHUB_EVIDENCE` or a
challenger concurrence on such a factual answer. Reconciliation still requires
current GitHub source receipts and leaves all topics unresolved, status BLOCKED,
and approval, automatic suppression, Inbox import and Forge authority false.
The Linear packet is not signed current truth and is not rechecked after every
model stage; it must not be substituted for the remaining authority checks.

## V2 private selection example

These identifiers are fictional format examples. Do not invoke them remotely.

~~~json
{
  "schema_version": 2,
  "target_issue": "example-org/sample-repo#123",
  "review_scope": "APP_REVIEW",
  "workspace": "example-workspace",
  "allowed_issue_prefixes": ["HIST"],
  "historical_issues": [
    {
      "id": "HIST-101",
      "scope": "APP_REVIEW",
      "focus": "prior decision",
      "team_id": "11111111-1111-1111-1111-111111111111",
      "project_id": "22222222-2222-2222-2222-222222222222"
    }
  ]
}
~~~

The existing `collect_linear_history.py` CLI selects the v1 or v2 reader from
the validated plan version. It writes exclusive-create, private mode-0600 files.
Changed/invalid collection writes no packet. V1 packets remain supported as
legacy title/description context; no automatic upgrade or new privileges occur.
No R720-AI deployment, credential provisioning or live Linear request is part
of this change. CI uses synthetic API responses and mocked model calls only.

Query fields were checked against the [official Linear SDK schema](https://github.com/linear/linear/blob/master/packages/sdk/src/schema.graphql)
and [pagination documentation](https://linear.app/developers/pagination) on
2026-11-05. Live credential permissions, response URLs and production behavior
remain NOT_VERIFIED. Status-transition history, edit histories, reactions,
attachments, semantic supersession/authority adjudication and broader GitHub
ADR/PR discovery remain separate work.
