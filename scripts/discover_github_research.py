"""Scoped ADR/document and PR discovery candidates for one GitHub review.

Read-only collector, never a reviewer: candidate matches are not accepted
evidence, approved decisions, new intake, Inbox entries or Forge work orders.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from collect_context import ReadOnlyHTTP, canonical, digest, read_bounded_json, read_private_key, snippet, valid_path, write_private
from evidence_context import GITHUB_ISSUE, HEX40, SCOPE
from recheck_github_sources import GitHubFreshnessClient

MAX_FILES = 8
MAX_PRS = 8
MAX_TREE = 2000
TERM = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _-]{2,59}\Z")
TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")


def validate_plan(plan, story, policy):
    if not isinstance(plan, dict) or set(plan) != {
            "schema_version", "target_issue", "review_scope", "repository", "document_prefixes", "terms"}:
        raise ValueError("Discovery requires exact scoped plan fields")
    target, repo, scope = plan["target_issue"], plan["repository"], plan["review_scope"]
    if (type(plan["schema_version"]) is not int or plan["schema_version"] != 1
            or not isinstance(target, str) or not GITHUB_ISSUE.fullmatch(target)
            or target != story.get("source_issue_id")
            or not isinstance(repo, str) or repo != target.split("#")[0]
            or any(part in (".", "..") for part in repo.split("/"))
            or repo not in policy.get("evidence_allowed_repositories", [])
            or not isinstance(scope, str) or not SCOPE.fullmatch(scope)
            or scope != story.get("review_scope") or scope != policy.get("review_scope")):
        raise ValueError("Discovery target/repository/scope must match the GitHub review")
    prefixes, terms = plan["document_prefixes"], plan["terms"]
    if (not isinstance(prefixes, list) or not 1 <= len(prefixes) <= 3
            or any(not isinstance(p, str) for p in prefixes) or len(set(prefixes)) != len(prefixes)):
        raise ValueError("Explicit document directories required")
    for prefix in prefixes:
        valid_path(prefix)
    if (not isinstance(terms, list) or not 1 <= len(terms) <= 4
            or any(not isinstance(t, str) or not TERM.fullmatch(t) or t != t.strip() for t in terms)
            or len({t.casefold() for t in terms}) != len(terms)):
        raise ValueError("Bounded literal search terms required; query qualifiers forbidden")


class GitHubResearchClient(GitHubFreshnessClient):
    def tree(self, repository, sha):
        commit = self._get("/repos/%s/git/commits/%s" % (repository, sha))
        tree = commit.get("tree") if isinstance(commit, dict) else None
        tree_sha = tree.get("sha") if isinstance(tree, dict) else None
        if (not isinstance(commit, dict) or commit.get("sha") != sha
                or not isinstance(tree_sha, str) or not HEX40.fullmatch(tree_sha)):
            raise ValueError("Discovery commit tree not pinned")
        value = self._get("/repos/%s/git/trees/%s" % (repository, tree_sha), {"recursive": 1})
        if (not isinstance(value, dict) or value.get("sha") != tree_sha
                or value.get("truncated") is not False or not isinstance(value.get("tree"), list)
                or len(value["tree"]) > MAX_TREE):
            raise ValueError("Repository tree incomplete or outside discovery bounds")
        return value["tree"]

    def pull_numbers(self, repository, term):
        # The operator supplies literal terms, never an arbitrary GitHub query.
        value = self._get("/search/issues", {
            "q": 'repo:%s is:pr in:title,body "%s"' % (repository, term), "per_page": MAX_PRS + 1,
        })
        if (not isinstance(value, dict) or value.get("incomplete_results") is not False
                or type(value.get("total_count")) is not int or not 0 <= value["total_count"] <= MAX_PRS
                or not isinstance(value.get("items"), list)
                or len(value["items"]) != value["total_count"]):
            raise ValueError("PR search incomplete or outside discovery bounds")
        result = []
        for item in value["items"]:
            if (not isinstance(item, dict) or type(item.get("number")) is not int or item["number"] < 1
                    or item["number"] in result or not isinstance(item.get("pull_request"), dict)
                    or item.get("html_url") != "https://github.com/%s/pull/%d" % (repository, item["number"])):
                raise ValueError("Search result is not a PR in the selected repository")
            result.append(item["number"])
        return result

    def pull(self, repository, number):
        value = self._get("/repos/%s/pulls/%d" % (repository, number))
        if (not isinstance(value, dict) or type(value.get("number")) is not int or value["number"] != number
                or value.get("html_url") != "https://github.com/%s/pull/%d" % (repository, number)
                or not isinstance(value.get("title"), str) or not value["title"].strip()
                or value.get("body") is not None and not isinstance(value["body"], str)
                or not isinstance(value.get("updated_at"), str) or not TIME.fullmatch(value["updated_at"])
                or value.get("state") not in ("open", "closed") or type(value.get("merged")) is not bool
                or type(value.get("draft")) is not bool):
            raise ValueError("PR identity/lifecycle response invalid")
        for key in ("base", "head"):
            obj = value.get(key)
            if (not isinstance(obj, dict) or not isinstance(obj.get("sha"), str) or not HEX40.fullmatch(obj["sha"])
                    or key == "base" and (not isinstance(obj.get("repo"), dict)
                                           or obj["repo"].get("full_name") != repository)):
                raise ValueError("PR repository or pinned revisions invalid")
        if value["merged"] and (value["state"] != "closed" or value["draft"]):
            raise ValueError("PR lifecycle contradiction")
        return {"number": number, "url": value["html_url"], "title": value["title"],
                "body": value.get("body") or "", "updated_at": value["updated_at"],
                "state": value["state"], "merged": value["merged"], "draft": value["draft"],
                "base_sha": value["base"]["sha"], "head_sha": value["head"]["sha"]}


def discover(plan, story, policy, github):
    validate_plan(plan, story, policy)
    repo, terms = plan["repository"], plan["terms"]
    target_number = int(plan["target_issue"].split("#")[1])
    target = github.issue(repo, target_number)
    target_snapshot = canonical({k: target.get(k) for k in (
        "number", "html_url", "title", "body", "updated_at", "comments", "state")})
    branch = github.default_branch(repo)
    head = github.commit(repo, branch)
    if not isinstance(head, str) or not HEX40.fullmatch(head):
        raise ValueError("Discovery repository revision not pinned")
    tree = github.tree(repo, head)
    paths = []
    for node in tree:
        if not isinstance(node, dict) or not isinstance(node.get("path"), str):
            raise ValueError("Malformed tree entry")
        path = node["path"]
        if any(path.startswith(prefix + "/") for prefix in plan["document_prefixes"]) and path.endswith(".md"):
            valid_path(path)
            if node.get("type") != "blob" or node.get("mode") != "100644" or path in paths:
                raise ValueError("Document must be a unique regular Markdown file")
            paths.append(path)
    if len(paths) > MAX_FILES:
        raise ValueError("Document directory selection too broad; narrow it explicitly")
    candidates = []
    for path in sorted(paths):
        text = github.file(repo, path, head)
        hits = [t for t in terms if t.casefold() in text.casefold()]
        if not hits:
            continue
        # snippet requires an exact substring; casefold can change Unicode length.
        match = re.search(re.escape(hits[0]), text, re.IGNORECASE)
        if match is None:
            raise ValueError("Document match cannot be represented as a source excerpt")
        excerpt = snippet(text, match.group())
        offset = text.find(excerpt)
        first = text.count("\n", 0, offset) + 1
        last = first + excerpt.count("\n")
        candidates.append({"source_kind": "DOCUMENT", "url": "https://github.com/%s/blob/%s/%s#L%d-L%d" % (
            repo, head, path, first, last), "revision": head, "path": path,
            "content_sha256": digest(text.encode()), "excerpt": excerpt,
            "excerpt_sha256": digest(excerpt.encode()), "matched_terms": hits})
    numbers = set()
    for term in terms:
        numbers.update(github.pull_numbers(repo, term))
        if len(numbers) > MAX_PRS:
            raise ValueError("Combined PR search exceeds bounded candidate count")
    pulls = {}
    for number in sorted(numbers):
        pr = github.pull(repo, number)
        text = pr["title"] + "\n\n" + pr["body"]
        if len(text.encode()) > 90_000:
            raise ValueError("PR description exceeds bounded size")
        hits = [t for t in terms if t.casefold() in text.casefold()]
        if not hits:
            raise ValueError("PR search result does not match its current description; recollect")
        match = re.search(re.escape(hits[0]), text, re.IGNORECASE)
        if match is None:
            raise ValueError("PR match cannot be represented as source excerpt")
        excerpt = snippet(text, match.group())
        pulls[number] = pr
        candidates.append({"source_kind": "PULL_REQUEST", "url": pr["url"],
            "revision": pr["updated_at"], "lifecycle": {k: pr[k] for k in (
                "state", "merged", "draft", "base_sha", "head_sha")},
            "content_sha256": digest(canonical(pr).encode()), "excerpt": excerpt,
            "excerpt_sha256": digest(excerpt.encode()), "matched_terms": hits})
    if any(canonical(github.pull(repo, n)) != canonical(pr) for n, pr in pulls.items()):
        raise ValueError("PR changed during discovery; recollect")
    if github.default_branch(repo) != branch or github.commit(repo, branch) != head:
        raise ValueError("Repository default branch changed during discovery; recollect")
    current_target = github.issue(repo, target_number)
    if target_snapshot != canonical({k: current_target.get(k) for k in (
            "number", "html_url", "title", "body", "updated_at", "comments", "state")}):
        raise ValueError("Target GitHub issue changed during discovery; recollect")
    for i, candidate in enumerate(candidates, 1):
        candidate.update(candidate_id="D-%03d" % i, authority="UNVERIFIED", selected_for_review=False)
    result = {
        "schema_version": 1, "kind": "clarity-github-research-discovery", "target_issue": plan["target_issue"],
        "review_scope": plan["review_scope"], "repository": repo, "default_branch": branch, "head_sha": head,
        "target_issue_revision": target["updated_at"],
        "story_sha256": digest(canonical(story).encode()), "policy_sha256": digest(canonical(policy).encode()),
        "selection_sha256": digest(canonical(plan).encode()), "selection": plan,
        "status": "CANDIDATES_ONLY", "documents_scanned": len(paths), "candidates": candidates,
        "search_completeness_authority": False, "current_policy_authority": False,
        "issue_intake_authority": False, "automatic_question_suppression_authority": False,
        "inbox_import_authority": False, "approval_authority": False, "forge_dispatch_authority": False,
    }
    if len(canonical(result).encode()) > 90_000:
        raise ValueError("Discovery output exceeds safe size")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "story", "policy", "github-key-file", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        plan, story, policy = [read_bounded_json(p, 250_000) for p in (args.plan, args.story, args.policy)]
        validate_plan(plan, story, policy)  # before credentials
        github = GitHubResearchClient(ReadOnlyHTTP(), read_private_key(args.github_key_file))
        result = discover(plan, story, policy, github)
        write_private(args.output, result)
        print("GitHub research candidates:", len(result["candidates"]))
        print("No intake, model calls, approval, Inbox import or Forge dispatch.")
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        print("BLOCKED: scoped GitHub research discovery failed", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
