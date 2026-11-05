"""Read-only current GitHub source-revision recheck for Clarity evidence.

This runs ONLY in an authorized GitHub READ collector, never the model
reviewer. Compares the original issue revision and SHA-pinned source
excerpts with live GitHub APIs; a moved default-branch HEAD or edited
issue is SOURCE_CHANGED. This is source integrity, NOT policy approval,
semantic sufficiency, Inbox authority or Forge permission.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit

from collect_context import (
    ReadOnlyHTTP, canonical, digest, read_bounded_json, read_private_key,
    write_private,
)
from collect_github_context import GitHubEvidenceClient, issue_text
from evidence_context import GITHUB_ISSUE, validate_evidence_packet
from question_freshness_attestation import attest_freshness, read_attestation_key
from export_review_questions import read_private_report
from github_discussion_snapshot import validate_snapshot

BRANCH = re.compile(r"[A-Za-z0-9._/-]{1,120}\Z")


class GitHubFreshnessClient(GitHubEvidenceClient):
    def default_branch(self, repository):
        owner, name = repository.split("/")
        result = self._get("/repos/%s/%s" % (owner, name))
        branch = result.get("default_branch")
        if (not isinstance(branch, str) or not BRANCH.fullmatch(branch)
                or ".." in branch.split("/")
                or any(part in ("", ".", "..") for part in branch.split("/"))):
            raise ValueError("GitHub default-branch metadata missing or invalid")
        return branch


def recheck(story, policy, evidence, github, *, discussion_snapshot=None, collector_key=None):
    """Verify all exact-source receipts; never claim ownership/approval."""
    validate_evidence_packet(evidence, story, policy)
    if (evidence["schema_version"] not in (2, 3)
            or not GITHUB_ISSUE.fullmatch(evidence["target_issue"])
            or evidence["freshness"] != "SOURCE_UNVERIFIED"):
        raise ValueError("Only original GitHub v2/v3 snapshots may be rechecked")
    originals = (validate_snapshot(discussion_snapshot, evidence, collector_key)
                 if evidence["schema_version"] == 3 else None)
    if evidence["schema_version"] == 2 and discussion_snapshot is not None:
        raise ValueError("Legacy evidence needs recollection; cannot retrofit an original snapshot")
    branch_heads = {}
    issue_originals = {}
    results = []
    discussion_results = []
    changed = False
    for source in evidence["sources"]:
        parsed = urlsplit(source["url"])
        bits = parsed.path.strip("/").split("/")
        repo = bits[0] + "/" + bits[1]
        kind = source["source_kind"]
        revision = source["revision"]
        if kind == "ISSUE":
            number = int(bits[3])
            selection = {
                "repository": repo, "number": number,
                "include_comments": True,
            }
            updated, content_hash, full_text = issue_text(github, selection)
            issue_originals[(repo, number)] = (updated, content_hash)
            current = updated
            content_matches = source["excerpt"] in full_text
            matched = (revision == updated and content_matches)
            if originals is not None:
                claimed_hash = originals[source["id"]]["discussion_sha256"]
                discussion_matches = claimed_hash == content_hash
                matched = matched and discussion_matches
                discussion_results.append({
                    "source_id": source["id"], "claimed_sha256": claimed_hash,
                    "observed_sha256": content_hash,
                    "status": "MATCHED" if discussion_matches else "SOURCE_CHANGED",
                })
        else:
            if kind not in ("CODE", "DOCUMENT", "TEST"):
                raise ValueError("Unexpected GitHub evidence source type")
            path = "/".join(bits[4:])
            content = github.file(repo, path, revision)
            content_matches = source["excerpt"] in content
            if repo not in branch_heads:
                branch = github.default_branch(repo)
                head = github.commit(repo, branch)
                branch_heads[repo] = (branch, head)
            current = branch_heads[repo][1]
            matched = (revision == current and content_matches)
        changed = changed or not matched
        results.append({
            "source_id": source["id"],
            "source_kind": kind,
            "claimed_revision": revision,
            "observed_revision": current,
            "content_matches": content_matches,
            "status": "MATCHED" if matched else "SOURCE_CHANGED",
        })
    # Fail closed on changes that occur DURING collection, even if all
    # initial source checks were coherent with the snapshot.
    for (repo, number), first in issue_originals.items():
        updated, body_hash, _ = issue_text(github, {
            "repository": repo, "number": number, "include_comments": True,
        })
        if (updated, body_hash) != first:
            changed = True
    for repo, (branch, head) in branch_heads.items():
        if github.default_branch(repo) != branch or github.commit(repo, branch) != head:
            changed = True
    result = {
        "schema_version": 2 if originals is not None else 1,
        "kind": "clarity-github-source-freshness-recheck",
        "target_issue": evidence["target_issue"],
        "review_scope": evidence["review_scope"],
        "evidence_sha256": digest(canonical(evidence).encode()),
        "story_sha256": evidence["story_sha256"],
        "policy_sha256": evidence["policy_sha256"],
        "recheck_status": "SOURCE_CHANGED" if changed else "MATCHED_AT_READ_TIME",
        "rechecked_sources": results,
        "github_network_rechecked": True,
        "owner_policy_authority_verified": False,
        "semantic_answer_sufficiency_verified": False,
        "automatic_question_suppression_authority": False,
        "inbox_import_authority": False,
        "approval_authority": False,
        "forge_dispatch_authority": False,
    }
    if originals is not None:
        result.update(
            original_discussion_receipt_sha256=digest(canonical(discussion_snapshot).encode()),
            discussion_integrity_status="SOURCE_CHANGED" if changed else "MATCHED_AT_READ_TIME",
            rechecked_discussions=discussion_results,
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--github-evidence", required=True, type=Path)
    parser.add_argument("--github-key-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--challenge", type=Path)
    parser.add_argument("--attestation-key-file", type=Path)
    parser.add_argument("--discussion-snapshot", type=Path)
    args = parser.parse_args()
    try:
        story = read_bounded_json(args.story, 250_000)
        policy = read_bounded_json(args.policy, 100_000)
        evidence = read_bounded_json(args.github_evidence, 100_000)
        # Verify approved repo/scope before touching token.
        validate_evidence_packet(evidence, story, policy)
        signed_args = (args.challenge, args.attestation_key_file, args.discussion_snapshot)
        if any(signed_args) and not all(signed_args):
            raise ValueError("Challenge, original discussion snapshot and collector key must be supplied together")
        challenge = read_private_report(args.challenge) if args.challenge else None
        key = read_attestation_key(args.attestation_key_file) if challenge is not None else None
        snapshot = read_private_report(args.discussion_snapshot) if args.discussion_snapshot else None
        if evidence["schema_version"] == 3 or snapshot is not None:
            validate_snapshot(snapshot, evidence, key)  # before GitHub credential/network
        challenge_sha = digest(canonical(challenge).encode()) if challenge is not None else None
        github = GitHubFreshnessClient(
            ReadOnlyHTTP(), read_private_key(args.github_key_file))
        started_at = int(time.time())
        result = recheck(story, policy, evidence, github,
                         discussion_snapshot=snapshot, collector_key=key)
        output = (attest_freshness(result, challenge_sha, key, started_at, int(time.time()))
                  if key is not None else result)
        write_private(args.output, output)
        print("GitHub snapshot recheck:", result["recheck_status"])
        print("Sources rechecked:", len(result["rechecked_sources"]))
        print("No issue mutation, owner approval, Inbox import or Forge dispatch.")
        return 0 if result["recheck_status"] == "MATCHED_AT_READ_TIME" else 3
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        print("BLOCKED: GitHub recheck could not establish source freshness",
              file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
