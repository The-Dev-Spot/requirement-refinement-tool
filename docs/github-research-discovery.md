# Focused GitHub ADR and PR discovery

`scripts/discover_github_research.py` finds research **candidates** before the
source selection and review steps. It runs only in an authorized read-only
collector, without a model, Inbox, issue writer or Forge capability.

The plan binds one existing canonical GitHub Issue to the exact story/policy
scope and the target repository's allowlist. The collector refuses a PR as
the target, even though PRs can be research context. It checks the target
issue before and after discovery and refuses changed descriptions/revisions.

## Retrieval

- The operator supplies 1–3 exact document-directory prefixes and 1–4 literal
  keyword phrases. Terms cannot contain query qualifiers, quotes or newlines.
- The collector resolves the actual default branch and commit, then the
  commit's **tree SHA**, before reading the recursive tree. Incomplete trees
  or more than 2,000 tree entries fail closed. This is a whole-tree bound;
  large repositories need a future bounded subtree walker.
- At most eight regular `.md` files under the selected directories are read
  at that commit. Symlinks, executable Markdown, duplicates and invalid paths
  are refused. Excerpts include pinned line URLs, full-content/excerpt hashes
  and the literal terms matched. A match is not proof of semantic relevance.
- A fixed `repo:<target> is:pr in:title,body "literal term"` search is made for
  each phrase. Results must be complete within eight PRs per query and eight
  unique PRs overall. No automatic pagination or cross-repository search is
  performed. Search snippets and search-returned URLs are not followed.
- Each PR is re-read from its fixed API endpoint, validating its repository,
  identity, body, lifecycle and base/head commit pins. PR descriptions are
  searched, including open, closed-unmerged and merged PRs. Fork head metadata
  can be recorded, but no fork content is fetched. PR discussion comments,
  reviews and changed-file patches are **not** collected in this slice.
- PR snapshots, the target issue and default-branch HEAD are checked again at
  the end. Moved/changed sources, search-index mismatches, API errors, oversized
  results or obvious credentials in emitted excerpts block output.

## Output and boundaries

The exclusive-create, mode-0600 private report binds selection, story/policy
hashes, issue revision and repository HEAD. Each candidate has a URL, revision,
excerpt/hash, matched terms and unverified authority. PR lifecycle data does not
prove deployment, current implementation, decision adoption or owner approval.

Reports always have status `CANDIDATES_ONLY`, with `selected_for_review: false`
on every result. All intake, search-completeness, current-policy, suppression,
Inbox, approval and Forge authority flags remain false. An empty result does
not prove no relevant evidence exists or that the owner must answer a question.
Source text is data and cannot authorize commands or modify the review contract.

This format is deliberately distinct from a Clarity evidence packet. It cannot
be passed to the reviewer, relevance gate, trusted reconciler or Inbox importer.
Select relevant document paths into a fresh authorized GitHub collection plan,
then collect the source-bound evidence and original discussion snapshot before
review. PR candidates need a separate provenance/freshness adapter before they
can be used by the question research stages. No candidate is auto-imported.
Linear remains separate read-only historical context; it never becomes intake.

## Future authorized invocation (not deployed)

The following selection uses fictional identifiers; do not run it remotely:

~~~json
{
  "schema_version": 1,
  "target_issue": "example-org/project#123",
  "review_scope": "APP_REVIEW",
  "repository": "example-org/project",
  "document_prefixes": ["docs/adr", "docs/architecture"],
  "terms": ["manual approval", "worker queue"]
}
~~~

~~~sh
python3 scripts/discover_github_research.py \
  --plan /private/research-selection.json \
  --story /private/story.json --policy /private/policy.json \
  --github-key-file /private/secrets/github-read.key \
  --output /private/research-candidates-unique.json
~~~

Only the read collector holds a GitHub credential; none is supplied to a model.
No credential, real source packet, live API call, paid model use or runtime
deployment is introduced by this change. Tests inject synthetic API responses.
The API approach follows GitHub's [REST search documentation](https://docs.github.com/en/rest/search/search)
and [Git tree API](https://docs.github.com/en/rest/git/trees); live integration,
provider search-index coverage and source authority remain NOT_VERIFIED.
