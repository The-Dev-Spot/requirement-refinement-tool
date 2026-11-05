"""GitHub-only Clarity context collector (v2 excerpts / v3 discussion binding).

Operational issues are GitHub Issues in their owning project repository.
Linear is not queried. This one-shot collector is read-only, uses explicit
allowlists, cannot issue a verdict and never authorizes Forge or ticket writes.
Historical v1 Linear evidence packets remain an archival format only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from collect_context import (
    GitHubRead, ReadOnlyHTTP, canonical, digest, read_bounded_json,
    read_private_key, snippet, source_entry, valid_path, write_private,
)
from evidence_context import GITHUB_ISSUE, HEX40, SCOPE, validate_evidence_packet
from github_discussion_snapshot import capture_snapshot
from question_freshness_attestation import read_attestation_key

MAX_SOURCES = 20
MAX_COMMENTS = 20
REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z\Z")


class GitHubEvidenceClient(GitHubRead):
    """Only fixed GitHub read endpoints for issues, comments and files."""

    @staticmethod
    def canonical_issue_url(repo, number):
        return "https://github.com/%s/issues/%d" % (repo, number)

    def issue(self, repository, number):
        owner, name = repository.split("/")
        result = self._get("/repos/%s/%s/issues/%d" % (owner, name, number))
        expected = self.canonical_issue_url(repository, number)
        if (not isinstance(result, dict)
                or "pull_request" in result
                or result.get("number") != number
                or result.get("html_url") != expected
                or not isinstance(result.get("title"), str)
                or not result["title"].strip()
                or result.get("body") is not None and
                    not isinstance(result.get("body"), str)
                or not isinstance(result.get("updated_at"), str)
                or not TIME.fullmatch(result["updated_at"])
                or not isinstance(result.get("comments"), int)
                or result["comments"] < 0):
            raise ValueError("GitHub issue invalid, replaced, or is a pull request")
        return result

    def comments(self, repository, number, expected_count):
        if expected_count > MAX_COMMENTS:
            raise ValueError("Too many GitHub issue comments for bounded review")
        if expected_count == 0:
            return []
        owner, name = repository.split("/")
        result = self._get("/repos/%s/%s/issues/%d/comments" %
                           (owner, name, number), {"per_page": MAX_COMMENTS + 1})
        if not isinstance(result, list) or len(result) != expected_count:
            raise ValueError("GitHub issue comments count changed or exceeded bounds")
        normalized = []
        seen = set()
        for comment in result:
            if (not isinstance(comment, dict)
                    or not isinstance(comment.get("id"), int)
                    or comment["id"] in seen
                    or not isinstance(comment.get("body"), str)
                    or not isinstance(comment.get("updated_at"), str)
                    or not TIME.fullmatch(comment["updated_at"])
                    or not isinstance(comment.get("user"), dict)
                    or not isinstance(comment["user"].get("login"), str)):
                raise ValueError("Malformed or duplicated GitHub issue comment")
            seen.add(comment["id"])
            normalized.append({
                "id": comment["id"],
                "body": comment["body"],
                "updated_at": comment["updated_at"],
                "author": comment["user"]["login"],
            })
        return normalized


def issue_identity(selection):
    return "%s#%d" % (selection["repository"], selection["number"])


def validate_plan(plan, story, policy):
    if not isinstance(plan, dict) or set(plan) != {
            "schema_version", "target_issue", "issues", "files"}:
        raise ValueError("GitHub-only plan requires exact fields")
    target = plan.get("target_issue")
    if (type(plan["schema_version"]) is not int
            or plan["schema_version"] != 2
            or not isinstance(target, str)
            or not GITHUB_ISSUE.fullmatch(target)
            or story.get("source_issue_id") != target):
        raise ValueError("Canonical GitHub issue target must match story")
    allowlist = policy.get("evidence_allowed_repositories")
    if (not isinstance(allowlist, list) or not 1 <= len(allowlist) <= 15
            or any(not isinstance(r, str) or not REPO.fullmatch(r)
                   for r in allowlist)
            or len(set(allowlist)) != len(allowlist)):
        raise ValueError("Explicit GitHub repository allowlist required")
    issues, files = plan["issues"], plan["files"]
    if (not isinstance(issues, list) or not 1 <= len(issues) <= 15
            or not isinstance(files, list) or len(files) > 10
            or len(issues) + len(files) > MAX_SOURCES):
        raise ValueError("GitHub evidence source count exceeds limits")
    ids = set()
    for entry in issues:
        if not isinstance(entry, dict) or set(entry) != {
                "repository", "number", "scope", "focus", "include_comments"}:
            raise ValueError("Malformed GitHub issue selection")
        if (not isinstance(entry["repository"], str)
                or entry["repository"] not in allowlist
                or type(entry["number"]) is not int
                or not 1 <= entry["number"] <= 2147483647
                or not isinstance(entry["scope"], str)
                or not SCOPE.fullmatch(entry["scope"])
                or not isinstance(entry["focus"], str) or len(entry["focus"]) > 100
                or type(entry["include_comments"]) is not bool):
            raise ValueError("Unauthorized GitHub issue selection")
        key = issue_identity(entry)
        if key in ids:
            raise ValueError("Duplicate GitHub issue selection")
        ids.add(key)
    if target not in ids:
        raise ValueError("Target GitHub issue not in source selection")
    seen_files = set()
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {
                "repository", "ref", "path", "scope", "kind", "focus"}:
            raise ValueError("Malformed GitHub file selection")
        if (not isinstance(entry["repository"], str)
                or entry["repository"] not in allowlist
                or entry["ref"] not in ("main", "master")
                or not isinstance(entry["scope"], str)
                or not SCOPE.fullmatch(entry["scope"])
                or entry["kind"] not in ("CODE", "TEST", "DOCUMENT")
                or not isinstance(entry["focus"], str) or len(entry["focus"]) > 100):
            raise ValueError("Unauthorized GitHub file selection")
        valid_path(entry["path"])
        key = (entry["repository"], entry["ref"], entry["path"])
        if key in seen_files:
            raise ValueError("Duplicate GitHub file selection")
        seen_files.add(key)
    return plan


def issue_text(client, selection):
    repo, number = selection["repository"], selection["number"]
    issue = client.issue(repo, number)
    comments = (client.comments(repo, number, issue["comments"])
                if selection["include_comments"] else [])
    # Explicitly check the issue again after fetching comments; a comment may
    # arrive during the read. The final collection stage checks once more.
    if selection["include_comments"]:
        after = client.issue(repo, number)
        if any(after.get(key) != issue.get(key) for key in (
                "updated_at", "comments", "title", "body", "state")):
            raise ValueError("GitHub issue changed during comment collection")
    text = issue["title"] + "\n\n" + (issue["body"] or "")
    for c in comments:
        text += ("\n\n[Comment %d by %s, updated %s]\n%s" %
                 (c["id"], c["author"], c["updated_at"], c["body"]))
    if len(text.encode("utf-8")) > 120_000:
        raise ValueError("Issue discussion exceeds bounded evidence size")
    # Hash structured records, not the rendered model excerpt. This avoids
    # ambiguity when issue text contains comment-like delimiters.
    record = {key: issue.get(key) for key in (
        "number", "html_url", "title", "body", "updated_at", "state")}
    record["comments"] = comments
    return issue["updated_at"], digest(canonical(record).encode()), text


def _collect(plan, story, policy, github):
    validate_plan(plan, story, policy)
    sources, issue_versions, branch_heads = [], {}, {}
    for entry in plan["issues"]:
        repository, number = entry["repository"], entry["number"]
        updated, content_hash, text = issue_text(github, entry)
        issue_versions[(repository, number)] = (updated, content_hash)
        excerpt = snippet(text, entry["focus"])
        sources.append(source_entry(
            len(sources) + 1, "github",
            github.canonical_issue_url(repository, number),
            updated, entry["scope"], "ISSUE", "UNVERIFIED", excerpt))
    for entry in plan["files"]:
        repository, ref, path = entry["repository"], entry["ref"], entry["path"]
        key = (repository, ref)
        if key not in branch_heads:
            branch_heads[key] = github.commit(repository, ref)
        sha = branch_heads[key]
        if not isinstance(sha, str) or not HEX40.fullmatch(sha):
            raise ValueError("GitHub source commit is not pinned")
        contents = github.file(repository, path, sha)
        excerpt = snippet(contents, entry["focus"])
        offset = contents.find(excerpt)
        if offset < 0:
            raise ValueError("GitHub file citation offset unavailable")
        first = contents.count("\n", 0, offset) + 1
        last = first + excerpt.count("\n")
        url = "https://github.com/%s/blob/%s/%s#L%d-L%d" % (
            repository, sha, path, first, last)
        sources.append(source_entry(
            len(sources) + 1, "github", url, sha,
            entry["scope"], entry["kind"],
            "IMPLEMENTATION" if entry["kind"] in ("CODE", "TEST")
            else "UNVERIFIED", excerpt))
    changed = False
    for entry in plan["issues"]:
        key = (entry["repository"], entry["number"])
        updated, body_hash, _ = issue_text(github, entry)
        changed = ((updated, body_hash) != issue_versions[key]) or changed
    for (repo, ref), old in branch_heads.items():
        changed = (github.commit(repo, ref) != old) or changed
    packet = {
        "schema_version": 2, "kind": "clarity-context-evidence",
        "target_issue": plan["target_issue"],
        "story_sha256": digest(canonical(story).encode()),
        "policy_sha256": digest(canonical(policy).encode()),
        "review_scope": story.get("review_scope", "LEGACY"),
        "freshness": "SOURCE_CHANGED" if changed else "SOURCE_UNVERIFIED",
        "sources": sources,
    }
    validate_evidence_packet(packet, story, policy)
    discussions = [{
        "source_id": source["id"], "url": source["url"],
        "revision": source["revision"],
        "discussion_sha256": issue_versions[(entry["repository"], entry["number"])][1],
    } for entry, source in zip(plan["issues"], sources)]
    return packet, discussions


def collect(plan, story, policy, github):
    """Legacy excerpt-only collection; cannot establish discussion integrity."""
    return _collect(plan, story, policy, github)[0]


def collect_with_snapshot(plan, story, policy, github, collector_key):
    validate_plan(plan, story, policy)
    if any(entry["include_comments"] is not True for entry in plan["issues"]):
        raise ValueError("Original snapshot requires comments for every selected issue")
    packet, discussions = _collect(plan, story, policy, github)
    packet["schema_version"] = 3
    packet["discussion_snapshot_sha256"] = digest(canonical(discussions).encode())
    validate_evidence_packet(packet, story, policy)
    # Changed collection fails rather than signing a seemingly coherent snapshot.
    return packet, capture_snapshot(packet, discussions, collector_key)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--story", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--github-key-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--snapshot-output", type=Path)
    parser.add_argument("--attestation-key-file", type=Path)
    args = parser.parse_args()
    try:
        plan = read_bounded_json(args.plan, 12_000)
        story = read_bounded_json(args.story, 250_000)
        policy = read_bounded_json(args.policy, 100_000)
        validate_plan(plan, story, policy)
        if bool(args.snapshot_output) != bool(args.attestation_key_file):
            raise ValueError("Snapshot output and collector attestation key must be paired")
        if args.snapshot_output and any(item["include_comments"] is not True for item in plan["issues"]):
            raise ValueError("Original snapshot requires comments for every selected issue")
        key = read_attestation_key(args.attestation_key_file) if args.snapshot_output else None
        github = GitHubEvidenceClient(ReadOnlyHTTP(),
                                      read_private_key(args.github_key_file))
        if key is not None:
            packet, snapshot = collect_with_snapshot(plan, story, policy, github, key)
        else:
            packet = collect(plan, story, policy, github)
        write_private(args.output, packet)
        if key is not None:
            write_private(args.snapshot_output, snapshot)
        print("GitHub evidence: %d citations, status=%s, sha256=%s" %
              (len(packet["sources"]), packet["freshness"],
               digest(canonical(packet).encode())))
        print("No Linear reads, issue writes, model calls, acceptance or Forge dispatch.")
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        print("BLOCKED: GitHub evidence retrieval or validation failed",
              file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
