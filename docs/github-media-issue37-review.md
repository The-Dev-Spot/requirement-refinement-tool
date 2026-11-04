# Controlled GitHub-only media update review — issue #37

**Selected issue:** [The-Dev-Spot/homelab#37](https://github.com/The-Dev-Spot/homelab/issues/37).

This is the first full current-issue **read-only** Clarity pilot after GitHub
collection and the protected Question Inbox were validated on R720-AI.
It replaces the synthetic issue #169 selection **only for this pilot**;
it does not replace the historical Linear review, change Linear, or
authorize Docker/Forge actions.

## Files

- `examples/github-media-issue-37-evidence-plan.json`: approved **source
  selection**, with one GitHub Issue and seven SHA-pinned GitHub code/doc
  files in the Homelab repo.
- `examples/github-media-issue-37-story.json`: **candidate**, not
  owner-ratified, nonbehavioral acceptance criteria for assessing updates.
- `examples/github-media-issue-37-policy-draft.json`: deliberately **draft
  and unapproved** scope decision register; ACTIVE denotes a repo-documented
  safety rule *claim*, **not** verified owner authority. Two explicit
  PENDING records forbid a positive acceptance verdict.

The issue mixes current WUD inventory and the reporting implementation.
The collector must always read the **current** issue revision and pin
matching repository content, not the 2026-11-03 screenshot as final truth.
The scheduled WUD job may update issue #37 while a review is underway;
source-changed evidence must be rerun.

## Sequence (manual, with real GitHub token confined to collector)

1. Verify/review the example story and policy as *proposed input* and
   stage private copies on the R720 host under
   `/opt/clarity-context-private/inputs` (UID10002, mode 0600).
2. In the **collector** (UID10002, GitHub Issues:read + Contents:read only),
   run `scripts/collect_github_context.py` using the media evidence plan.
   Store a new, private mode-0600 evidence JSON; expect eight source
   citations and `SOURCE_UNVERIFIED`.
3. Copy only the private story, policy and evidence packet into
   `/opt/clarity-pilot-private/inputs` (UID10001, mode 0600).
   **Never transfer any GitHub token, Docker socket, Claude auth state,
   or persistent data between containers.** Keep reviewer and collector
   homes isolated.
4. Run the independently authenticated reviewer in the **separate**
   `clarity-pilot` image, pinned to the version of Clarity that implements
   GitHub-only evidence (requires refreshed image; old
   `dd3ecc...` HOM-1972 image cannot perform this pilot).
   For the *explicit* draft-policy benchmark use
   `--pilot-with-draft-policy` and a specifically selected model/budget.
   The verdict must remain `BLOCKED` even if reviewers find no issues:
   DoR not adopted, risk register DRAFT, pending authority decisions and
   source authority unverified.
5. If (and only if) three independent reviewer outputs with valid receipts
   and the exact **raw file hashes** exist, use
   `scripts/preview_github_review.py --report ...` to generate
   deduplicated owner question topics. A meaningful blocked review can
   produce questions without permission to implement.
6. After inspecting that private preview and reconfirming source revision,
   manually import a copy using the Inbox's
   `import-github-preview`. Its new provenance sidecar preserves
   reviewer IDs and GitHub citation URLs; answers remain
   `ANSWER_RECORDED_PENDING_SOURCE_UPDATE`.
7. Reconcile answers into the canonical GitHub issue through a separate,
   independently authorized write service, **then** collect/review fresh
   revisions before independent acceptance. The issue `#37` automatic
   WUD updates must not be mistaken for owner approval.

## Risk boundaries and acceptance of this pilot

- **Safe:** read issue/docs, ask questions, record owner answers privately.
- **Not authorized:** update an image, pull or restart any container,
  mutate GitHub/Linear from Clarity, grant `ACCEPTED_FOR_FORGE`, or
  trigger a deploy workflow.
- **Plex:** verify backup/restore readiness and playback smoke test.
- **qBittorrent:** shared Gluetun namespace means pull/restart decisions
  require a separate VPN-group plan and port-forward/kill-switch checks.
- **Traefik:** preserve TLS, Cloudflare and authenticated routing.
- **WUD tags `latest`:** do not assume that a changed digest equals a
  vetted application version.
- **Credentials:** only the collector sees the GitHub read token; only
  Clarity pilot sees its own Claude login; only the standalone Inbox sees
  its Access-authenticated answer database.

Track end-to-end question integration in
[homelab #172](https://github.com/The-Dev-Spot/homelab/issues/172).
The media maintenance tracker remains
[homelab #37](https://github.com/The-Dev-Spot/homelab/issues/37).
