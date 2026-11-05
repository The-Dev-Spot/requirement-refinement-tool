"""Optional Linear *history-only* reader for GitHub-targeted Clarity reviews.

Separate from GitHub intake and reviewer containers: this process reads only
explicitly approved, project-scoped historical Linear IDs. No issue discovery,
Linear mutation, GitHub writes, model calls, question suppression, acceptance
or Forge dispatch. Its output is private, unverified historical context.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from collect_context import (
    LinearRead, ReadOnlyHTTP, canonical, digest, read_bounded_json,
    read_private_key, snippet, write_private,
)
from evidence_context import GITHUB_ISSUE, SCOPE
from linear_history_details import (
    LinearHistoryRead, context_from_record, normalize_discussion, valid_uuid,
    validate_context,
)

ISSUE_ID = re.compile(r"[A-Z][A-Z0-9]+-[1-9][0-9]*\Z")
PREFIX = re.compile(r"[A-Z][A-Z0-9]{1,12}\Z")
WORKSPACE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9-]{2,79}\Z")
MAX_ISSUES = 12
MAX_PACKET = 90_000


def validate_plan(plan, story, policy):
    expected = {"schema_version", "target_issue", "review_scope", "workspace",
                "allowed_issue_prefixes", "historical_issues"}
    if not isinstance(plan, dict) or set(plan) != expected:
        raise ValueError("History plan must have exact approved fields")
    target = plan["target_issue"]
    scope = plan["review_scope"]
    if (type(plan["schema_version"]) is not int or plan["schema_version"] not in (1, 2)
            or not isinstance(target, str) or not GITHUB_ISSUE.fullmatch(target)
            or story.get("source_issue_id") != target):
        raise ValueError("History may only support an existing GitHub issue target")
    if (not isinstance(scope, str) or not SCOPE.fullmatch(scope)
            or story.get("review_scope") != scope
            or policy.get("review_scope") != scope):
        raise ValueError("History scope must match current review scope")
    allowed_repos = policy.get("evidence_allowed_repositories")
    if (not isinstance(allowed_repos, list)
            or target.split("#")[0] not in allowed_repos):
        raise ValueError("GitHub target is not an allowlisted repository")
    workspace = plan["workspace"]
    if not isinstance(workspace, str) or not WORKSPACE.fullmatch(workspace):
        raise ValueError("Linear workspace selection invalid")
    allowed = plan["allowed_issue_prefixes"]
    if (not isinstance(allowed, list) or not 1 <= len(allowed) <= 8
            or any(not isinstance(x, str) or not PREFIX.fullmatch(x)
                   for x in allowed)
            or len(set(allowed)) != len(allowed)):
        raise ValueError("Historical issue prefixes must be explicitly scoped")
    items = plan["historical_issues"]
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_ISSUES:
        raise ValueError("Historical items must be explicit and bounded")
    seen = set()
    for item in items:
        fields = {"id", "scope", "focus"}
        if plan["schema_version"] == 2:
            fields |= {"team_id", "project_id"}
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError("Historical issue selection invalid")
        iid = item["id"]
        if (not isinstance(iid, str) or not ISSUE_ID.fullmatch(iid)
                or iid.split("-")[0] not in allowed or iid in seen
                or item["scope"] != scope
                or not isinstance(item["focus"], str)
                or not 4 <= len(item["focus"]) <= 120):
            raise ValueError("Historical issue outside approved project or scope")
        if plan["schema_version"] == 2 and (
                not valid_uuid(item["team_id"])
                or item["project_id"] is not None and not valid_uuid(item["project_id"])):
            raise ValueError("Detailed history requires explicit team and project IDs")
        seen.add(iid)
    return plan


def collect_history(plan, story, policy, linear):
    """Read selected historical issues twice to detect intra-run changes."""
    validate_plan(plan, story, policy)
    if plan["schema_version"] == 2:
        return collect_detailed_history(plan, story, policy, linear)
    sources = []
    original = {}
    workspace = plan["workspace"]
    for n, entry in enumerate(plan["historical_issues"], 1):
        iid = entry["id"]
        item = linear.issue(iid)
        body = item["title"] + "\n\n" + item["description"]
        if len(body.encode("utf-8")) > 90_000:
            raise ValueError("Historical item exceeds size bound")
        excerpt = snippet(body, entry["focus"])
        original[iid] = (item["updatedAt"], digest(body.encode()))
        sources.append({
            "id": "L-%03d" % n,
            "provider": "linear",
            "source_kind": "HISTORICAL_ISSUE",
            "source_issue_id": iid,
            "url": "https://linear.app/%s/issue/%s" % (workspace, iid),
            "revision": item["updatedAt"],
            "scope": entry["scope"],
            "project_mapping": "OPERATOR_SELECTED_UNVERIFIED",
            "authority": "HISTORICAL_UNVERIFIED",
            "excerpt": excerpt,
            "excerpt_sha256": digest(excerpt.encode()),
        })
    changed = False
    for entry in plan["historical_issues"]:
        iid = entry["id"]
        item = linear.issue(iid)
        body = item["title"] + "\n\n" + item["description"]
        if (item["updatedAt"], digest(body.encode())) != original[iid]:
            changed = True
    result = {
        "schema_version": 1,
        "kind": "clarity-linear-history-context",
        "target_issue": plan["target_issue"],
        "review_scope": plan["review_scope"],
        "story_sha256": digest(canonical(story).encode()),
        "policy_sha256": digest(canonical(policy).encode()),
        "selection_sha256": digest(canonical(plan).encode()),
        "status": "SOURCE_CHANGED" if changed else "SOURCE_UNVERIFIED",
        "historical_sources": sources,
        "approval_authority": False,
        "issue_intake_authority": False,
        "forge_dispatch_authority": False,
        "current_policy_authority": False,
    }
    if len(canonical(result).encode()) > MAX_PACKET:
        raise ValueError("History packet too large")
    return result


def collect_detailed_history(plan, story, policy, linear):
    """Current historical issue status/comments, not a status-transition audit log."""
    validate_plan(plan, story, policy)
    if plan["schema_version"] != 2:
        raise ValueError("Detailed historical collection requires a v2 plan")
    sources, originals = [], {}
    for n, entry in enumerate(plan["historical_issues"], 1):
        record = normalize_discussion(linear.history_issue(
            entry["id"], selection=entry, workspace=plan["workspace"]), entry, plan["workspace"])
        originals[entry["id"]] = digest(canonical(record).encode())
        body = record["title"] + "\n\n" + record["description"]
        focus = entry["focus"]
        if not any(focus.casefold() in text.casefold()
                   for text in [body] + [c["body"] for c in record["comments"]]):
            raise ValueError("Selected historical focus not found in issue or comments")
        excerpt = snippet(body, focus if focus.casefold() in body.casefold() else "")
        context = context_from_record(record, focus)
        validate_context(context, entry, plan["workspace"])
        sources.append({
            "id": "L-%03d" % n, "provider": "linear", "source_kind": "HISTORICAL_ISSUE",
            "source_issue_id": entry["id"], "url": "https://linear.app/%s/issue/%s" % (plan["workspace"], entry["id"]),
            "revision": record["updated_at"], "scope": entry["scope"],
            "project_mapping": "API_IDS_MATCH_OPERATOR_SELECTION", "authority": "HISTORICAL_UNVERIFIED",
            "excerpt": excerpt, "excerpt_sha256": digest(excerpt.encode()), "history_context": context,
        })
    changed = False
    for entry in plan["historical_issues"]:
        record = normalize_discussion(linear.history_issue(
            entry["id"], selection=entry, workspace=plan["workspace"]), entry, plan["workspace"])
        changed = digest(canonical(record).encode()) != originals[entry["id"]] or changed
    result = {
        "schema_version": 2, "kind": "clarity-linear-history-context",
        "target_issue": plan["target_issue"], "review_scope": plan["review_scope"],
        "story_sha256": digest(canonical(story).encode()), "policy_sha256": digest(canonical(policy).encode()),
        "selection_sha256": digest(canonical(plan).encode()), "selection": plan,
        "status": "SOURCE_CHANGED" if changed else "SOURCE_UNVERIFIED", "historical_sources": sources,
        "approval_authority": False, "issue_intake_authority": False,
        "forge_dispatch_authority": False, "current_policy_authority": False,
    }
    if len(canonical(result).encode()) > MAX_PACKET:
        raise ValueError("Detailed historical packet exceeds safe size")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--story", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--linear-key-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        plan = read_bounded_json(args.plan, 12_000)
        story = read_bounded_json(args.story, 250_000)
        policy = read_bounded_json(args.policy, 100_000)
        validate_plan(plan, story, policy)  # validate *before* reading credential
        reader = LinearHistoryRead if plan["schema_version"] == 2 else LinearRead
        linear = reader(ReadOnlyHTTP(), read_private_key(args.linear_key_file))
        packet = collect_history(plan, story, policy, linear)
        if packet["status"] == "SOURCE_CHANGED":
            raise ValueError("Linear history changed during retrieval")
        write_private(args.output, packet)
        print("Historical Linear citations:", len(packet["historical_sources"]))
        print("Status:", packet["status"], "(no current policy authority)")
        print("No Linear/GitHub writes, model calls, acceptance or Forge dispatch.")
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        print("BLOCKED: scoped historical Linear context validation failed",
              file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
