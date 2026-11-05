"""Explicit document selection -> fresh private GitHub evidence collection.

Read collector only. PR candidates need a separate adapter and are refused.
Selection is not requirements approval, model authorization or Forge dispatch.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import stat
import sys

from collect_context import ReadOnlyHTTP, read_private_key, valid_path, write_private
from collect_github_context import collect_with_snapshot, validate_plan as validate_collection_plan
from discover_github_research import GitHubResearchClient, validate_plan as validate_discovery_plan, TIME
from evidence_context import canonical, digest, HEX40, HEX64, validate_evidence_packet
from github_discussion_snapshot import validate_snapshot
from question_freshness_attestation import read_attestation_key

FLAGS = ("search_completeness_authority", "current_policy_authority", "issue_intake_authority",
         "automatic_question_suppression_authority", "inbox_import_authority", "approval_authority", "forge_dispatch_authority")
FILES = ("discovery.json", "selection.json", "collection-plan.json", "evidence.json", "discussion-snapshot.json")


def read_snapshot(path):
    """Read one immutable byte snapshot through an owner-only, non-symlink FD."""
    fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077
                or not 0 < info.st_size <= 1_000_000):
            raise ValueError("Private bounded regular JSON file required")
        raw = stream.read(1_000_001)
    if len(raw) != info.st_size:
        raise ValueError("Private JSON changed during read")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError("Private JSON object required")
    canonical(value)  # refuse NaN and unsupported values
    return value, digest(raw)


def compile_selection(discovery, selection, story, policy):
    expected = {"schema_version", "kind", "target_issue", "review_scope", "repository", "default_branch",
                "head_sha", "target_issue_revision", "story_sha256", "policy_sha256", "selection_sha256",
                "selection", "status", "documents_scanned", "candidates", *FLAGS}
    if (not isinstance(discovery, dict) or set(discovery) != expected
            or type(discovery["schema_version"]) is not int or discovery["schema_version"] != 1
            or discovery["kind"] != "clarity-github-research-discovery" or discovery["status"] != "CANDIDATES_ONLY"
            or any(discovery[k] is not False for k in FLAGS)
            or discovery["story_sha256"] != digest(canonical(story).encode())
            or discovery["policy_sha256"] != digest(canonical(policy).encode())):
        raise ValueError("Discovery binding or authority differs")
    validate_discovery_plan(discovery["selection"], story, policy)
    if (discovery["selection_sha256"] != digest(canonical(discovery["selection"]).encode())
            or any(discovery[k] != discovery["selection"][k] for k in ("target_issue", "review_scope", "repository"))
            or discovery["default_branch"] not in ("main", "master")
            or not isinstance(discovery["head_sha"], str) or not HEX40.fullmatch(discovery["head_sha"])
            or not isinstance(discovery["target_issue_revision"], str) or not TIME.fullmatch(discovery["target_issue_revision"])
            or type(discovery["documents_scanned"]) is not int or not 0 <= discovery["documents_scanned"] <= 8):
        raise ValueError("Discovery plan or source revision differs")
    if (not isinstance(selection, dict) or set(selection) != {
            "schema_version", "kind", "target_issue", "discovery_sha256", "candidate_ids"}
            or type(selection["schema_version"]) is not int or selection["schema_version"] != 1
            or selection["kind"] != "clarity-discovery-document-selection"
            or selection["target_issue"] != discovery["target_issue"]
            or selection["discovery_sha256"] != digest(canonical(discovery).encode())):
        raise ValueError("Explicit selection must bind the exact discovery report")
    ids = selection["candidate_ids"]
    if (not isinstance(ids, list) or not 1 <= len(ids) <= 8
            or any(not isinstance(x, str) for x in ids) or len(set(ids)) != len(ids)):
        raise ValueError("Select 1..8 unique document candidates explicitly")
    candidates = discovery["candidates"]
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 16:
        raise ValueError("Discovery candidates missing or unbounded")
    index = {}
    for candidate in candidates:
        if (not isinstance(candidate, dict) or not isinstance(candidate.get("candidate_id"), str)
                or not re.fullmatch(r"D-[0-9]{3}", candidate["candidate_id"])
                or candidate["candidate_id"] in index or candidate.get("authority") != "UNVERIFIED"
                or candidate.get("selected_for_review") is not False
                or candidate.get("source_kind") not in ("DOCUMENT", "PULL_REQUEST")):
            raise ValueError("Invalid candidate identity or authority")
        index[candidate["candidate_id"]] = candidate
    if (sum(c["source_kind"] == "DOCUMENT" for c in candidates) > discovery["documents_scanned"]
            or sum(c["source_kind"] == "PULL_REQUEST" for c in candidates) > 8):
        raise ValueError("Discovery candidate counts exceed recorded coverage")
    repo, scope = discovery["repository"], discovery["review_scope"]
    files = []
    for cid in ids:
        item = index.get(cid)
        if item is None or item["source_kind"] != "DOCUMENT":
            raise ValueError("Only known document candidates are supported; PR adapter is not available")
        if set(item) != {"candidate_id", "authority", "selected_for_review", "source_kind", "url", "revision",
                         "path", "content_sha256", "excerpt", "excerpt_sha256", "matched_terms"}:
            raise ValueError("Document candidate contract differs")
        path = valid_path(item["path"])
        hits = item["matched_terms"]
        if (not path.endswith(".md")
                or not any(path.startswith(p + "/") for p in discovery["selection"]["document_prefixes"])
                or item["revision"] != discovery["head_sha"]
                or not isinstance(item["content_sha256"], str) or not HEX64.fullmatch(item["content_sha256"])
                or not isinstance(item["excerpt"], str) or not 1 <= len(item["excerpt"]) <= 3200
                or item["excerpt_sha256"] != digest(item["excerpt"].encode())
                or not isinstance(hits, list) or not hits or any(t not in discovery["selection"]["terms"] for t in hits)
                or not isinstance(item["url"], str) or not re.fullmatch(
                    re.escape("https://github.com/%s/blob/%s/%s" % (repo, discovery["head_sha"], path))
                    + r"#L[1-9][0-9]*-L[1-9][0-9]*", item["url"])):
            raise ValueError("Document candidate source/provenance differs")
        files.append({"repository": repo, "ref": discovery["default_branch"], "path": path,
                      "scope": scope, "kind": "DOCUMENT", "focus": hits[0]})
    plan = {"schema_version": 2, "target_issue": discovery["target_issue"],
            "issues": [{"repository": repo, "number": int(discovery["target_issue"].split("#")[1]),
                        "scope": scope, "focus": "", "include_comments": True}], "files": files}
    validate_collection_plan(plan, story, policy)
    return plan


def verify_selected_sources(discovery, selection, evidence):
    selected = {c["candidate_id"]: c for c in discovery["candidates"]}
    sources = evidence["sources"]
    if len(sources) != len(selection["candidate_ids"]) + 1:
        raise ValueError("Selected evidence coverage differs")
    if any(s["scope"] != discovery["review_scope"] for s in sources):
        raise ValueError("Selected evidence scope differs")
    target_url = "https://github.com/%s/issues/%s" % tuple(discovery["target_issue"].split("#"))
    if (sources[0]["source_kind"] != "ISSUE" or sources[0]["url"] != target_url
            or sources[0]["revision"] != discovery["target_issue_revision"]):
        raise ValueError("Selected target issue revision differs")
    for cid, source in zip(selection["candidate_ids"], sources[1:]):
        item = selected[cid]
        if (source["source_kind"] != "DOCUMENT" or source["url"] != item["url"]
                or source["revision"] != discovery["head_sha"] or source["excerpt"] != item["excerpt"]):
            raise ValueError("Collected source differs from selected document")


def recollect(discovery, selection, story, policy, github, collector_key):
    plan = compile_selection(discovery, selection, story, policy)
    repo, branch, head = discovery["repository"], discovery["default_branch"], discovery["head_sha"]
    if github.default_branch(repo) != branch or github.commit(repo, branch) != head:
        raise ValueError("Discovery is stale; recollect candidates")
    index = {c["candidate_id"]: c for c in discovery["candidates"]}
    for cid in selection["candidate_ids"]:
        item = index[cid]
        text = github.file(repo, item["path"], head)
        if digest(text.encode()) != item["content_sha256"] or item["excerpt"] not in text:
            raise ValueError("Selected document no longer matches pinned content")
    evidence, snapshot = collect_with_snapshot(plan, story, policy, github, collector_key)
    verify_selected_sources(discovery, selection, evidence)
    if github.default_branch(repo) != branch or github.commit(repo, branch) != head:
        raise ValueError("Default branch changed during selected collection")
    return {"discovery.json": discovery, "selection.json": selection, "collection-plan.json": plan,
            "evidence.json": evidence, "discussion-snapshot.json": snapshot}


def write_collection(directory, artifacts, story, policy):
    root = Path(directory)
    root.mkdir(mode=0o700, exist_ok=False)
    os.chmod(root, 0o700)
    for filename in FILES:
        write_private(root / filename, artifacts[filename])
    receipt = {"schema_version": 1, "kind": "clarity-selected-evidence-collection",
               "status": "COLLECTED_SOURCE_UNVERIFIED", "target_issue": story["source_issue_id"],
               "story_sha256": digest(canonical(story).encode()), "policy_sha256": digest(canonical(policy).encode()),
               "files": {name: digest((canonical(artifacts[name]) + "\n").encode()) for name in FILES},
               "selection_authority": "OPERATOR_SELECTED_UNVERIFIED", **{flag: False for flag in FLAGS}}
    write_private(root / "collection-receipt.json", receipt)  # completion marker, always last


def load_collection(directory, story, policy, collector_key):
    root = Path(directory)
    if root.is_symlink() or not root.is_dir() or stat.S_IMODE(root.stat().st_mode) & 0o077:
        raise ValueError("Private collection directory required")
    receipt, _ = read_snapshot(root / "collection-receipt.json")
    expected = {"schema_version", "kind", "status", "target_issue", "story_sha256", "policy_sha256",
                "files", "selection_authority", *FLAGS}
    if (set(receipt) != expected or type(receipt["schema_version"]) is not int or receipt["schema_version"] != 1
            or receipt["kind"] != "clarity-selected-evidence-collection" or receipt["status"] != "COLLECTED_SOURCE_UNVERIFIED"
            or receipt["target_issue"] != story["source_issue_id"] or receipt["selection_authority"] != "OPERATOR_SELECTED_UNVERIFIED"
            or receipt["story_sha256"] != digest(canonical(story).encode())
            or receipt["policy_sha256"] != digest(canonical(policy).encode())
            or not isinstance(receipt["files"], dict) or set(receipt["files"]) != set(FILES)
            or any(receipt[k] is not False for k in FLAGS)):
        raise ValueError("Collection receipt binding or authority differs")
    values, hashes = {}, {}
    for filename in FILES:
        values[filename], hashes[filename] = read_snapshot(root / filename)
        if hashes[filename] != receipt["files"][filename]:
            raise ValueError("Collection file differs from completion receipt")
    plan = compile_selection(values["discovery.json"], values["selection.json"], story, policy)
    if canonical(plan) != canonical(values["collection-plan.json"]):
        raise ValueError("Collection plan differs from explicit selection")
    evidence = values["evidence.json"]
    validate_evidence_packet(evidence, story, policy)
    validate_snapshot(values["discussion-snapshot.json"], evidence, collector_key)
    verify_selected_sources(values["discovery.json"], values["selection.json"], evidence)
    return values, hashes


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("discovery", "selection", "story", "policy", "github-key-file", "collector-key-file", "output-dir"):
        p.add_argument("--" + name, required=True, type=Path)
    args = p.parse_args()
    try:
        discovery, selection, story, policy = [read_snapshot(path)[0] for path in (
            args.discovery, args.selection, args.story, args.policy)]
        compile_selection(discovery, selection, story, policy)  # before credentials
        key = read_attestation_key(args.collector_key_file)
        github = GitHubResearchClient(ReadOnlyHTTP(), read_private_key(args.github_key_file))
        values = recollect(discovery, selection, story, policy, github, key)
        write_collection(args.output_dir, values, story, policy)
        print("Private selected document evidence collected; no review, approval or dispatch.")
        return 0
    except (OSError, ValueError, KeyError, TypeError, UnicodeError):
        print("BLOCKED: selected discovery collection failed", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
