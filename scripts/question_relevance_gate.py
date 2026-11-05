"""Offline, non-authoritative question relevance gate for *GitHub* review targets.

Replays the independent three-stage report and current pinned GitHub evidence
before applying explicitly proposed dispositions. Neither model assertions nor
historical Linear text can silently approve/suppress questions. No network,
provider calls, Inbox writes, issue edits or Forge dispatch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

from evidence_context import GITHUB_ISSUE, canonical, digest, validate_evidence_packet
from export_review_questions import read_private_report
from preview_github_review import prepare
from quality_review import write_private_report

ID = re.compile(r"topic-[0-9a-f]{20}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
HIST_ID = re.compile(r"L-[0-9]{3}\Z")
DISPOSITIONS = frozenset((
    "ANSWERED_BY_GITHUB_EVIDENCE", "NEEDS_TECHNICAL_VERIFICATION",
    "NEEDS_OWNER_DECISION", "DUPLICATE_OF",
))
MAX_PROPOSALS = 150
MAX_HISTORY = 12


def sha_file(path):
    return digest(Path(path).read_bytes())


def validate_history(history, story, policy):
    """Verify historical context binding, not its approval or project authority."""
    if history is None:
        return {}
    expected = {
        "schema_version", "kind", "target_issue", "review_scope",
        "story_sha256", "policy_sha256", "selection_sha256", "status",
        "historical_sources", "approval_authority", "issue_intake_authority",
        "forge_dispatch_authority", "current_policy_authority",
    }
    if not isinstance(history, dict) or set(history) != expected:
        raise ValueError("Historical evidence contract differs")
    if (type(history["schema_version"]) is not int or history["schema_version"] != 1
            or history["kind"] != "clarity-linear-history-context"
            or history["target_issue"] != story.get("source_issue_id")
            or not GITHUB_ISSUE.fullmatch(history["target_issue"])
            or history["review_scope"] != story.get("review_scope")
            or history["review_scope"] != policy.get("review_scope")
            or history["story_sha256"] != digest(canonical(story).encode())
            or history["policy_sha256"] != digest(canonical(policy).encode())
            or not isinstance(history["selection_sha256"], str)
            or not SHA.fullmatch(history["selection_sha256"])
            or history["status"] != "SOURCE_UNVERIFIED"):
        raise ValueError("Historical packet is not bound to current GitHub review")
    if any(history.get(flag) is not False for flag in (
            "approval_authority", "issue_intake_authority",
            "forge_dispatch_authority", "current_policy_authority")):
        raise ValueError("Historical evidence cannot assert current authority")
    sources = history["historical_sources"]
    if not isinstance(sources, list) or not 1 <= len(sources) <= MAX_HISTORY:
        raise ValueError("Historical sources not bounded")
    seen = set()
    for s in sources:
        if not isinstance(s, dict) or set(s) != {
            "id", "provider", "source_kind", "source_issue_id", "url",
            "revision", "scope", "project_mapping", "authority",
            "excerpt", "excerpt_sha256",
        }:
            raise ValueError("Invalid historical source shape")
        ref = s["id"]
        if not isinstance(ref, str) or not HIST_ID.fullmatch(ref) or ref in seen:
            raise ValueError("Historical source identity duplicated or invalid")
        seen.add(ref)
        url = urlsplit(s["url"]) if isinstance(s["url"], str) else None
        issue_id = s["source_issue_id"]
        if (s["provider"] != "linear"
                or s["source_kind"] != "HISTORICAL_ISSUE"
                or s["authority"] != "HISTORICAL_UNVERIFIED"
                or s["project_mapping"] != "OPERATOR_SELECTED_UNVERIFIED"
                or s["scope"] != history["review_scope"]
                or not isinstance(issue_id, str)
                or not re.fullmatch(r"[A-Z][A-Z0-9]+-[1-9][0-9]*", issue_id)
                or url is None or url.scheme != "https"
                or url.netloc != "linear.app" or url.query or url.fragment
                or not re.fullmatch(r"/[A-Za-z0-9-]+/issue/" + re.escape(issue_id),
                                    url.path)
                or not isinstance(s["revision"], str) or not s["revision"]
                or not isinstance(s["excerpt"], str) or not s["excerpt"].strip()
                or len(s["excerpt"]) > 3200
                or not isinstance(s["excerpt_sha256"], str)
                or digest(s["excerpt"].encode()) != s["excerpt_sha256"]):
            raise ValueError("Historical source content or provenance invalid")
    return {item["id"]: item for item in sources}


def replay_preview(story, policy, evidence, report, preview, raw_hashes):
    """Exact digest match prevents forged owner-facing question inventories."""
    validate_evidence_packet(evidence, story, policy)
    expected = prepare(
        story, policy, evidence, report=report,
        story_file_sha=raw_hashes[0],
        policy_file_sha=raw_hashes[1],
        evidence_file_sha=raw_hashes[2],
    )
    if canonical(expected) != canonical(preview):
        raise ValueError("Question preview differs from validated review and evidence")
    if (preview["review_status"] != "REVIEW_QUESTIONS_PROPOSED"
            or preview["review_gate_status"] not in ("BLOCKED", "FAIL")
            or preview["source_status"] != "SOURCE_UNVERIFIED"
            or preview["target_issue"] != story["source_issue_id"]
            or preview["policy_review_contract"] != "VALID"):
        raise ValueError("Only completed, blocked GitHub review may be triaged")
    return expected


def validate_proposals(proposals, preview, github_sources, historical_sources):
    if proposals is None:
        return {}
    if not isinstance(proposals, dict) or set(proposals) != {
            "schema_version", "kind", "target_issue", "review_report_sha256",
            "decisions"}:
        raise ValueError("Malformed decision proposals")
    if (type(proposals["schema_version"]) is not int
            or proposals["schema_version"] != 1
            or proposals["kind"] != "clarity-question-disposition-proposals"
            or proposals["target_issue"] != preview["target_issue"]
            or proposals["review_report_sha256"] != preview["review_report_sha256"]):
        raise ValueError("Proposals must be tied to one exact GitHub review")
    decisions = proposals["decisions"]
    if not isinstance(decisions, list) or len(decisions) > MAX_PROPOSALS:
        raise ValueError("Too many decision proposals")
    topics = {x["topic_id"] for x in preview["question_topics"]}
    seen = {}
    for entry in decisions:
        if not isinstance(entry, dict) or set(entry) != {
                "topic_id", "disposition", "rationale", "answer",
                "evidence", "duplicate_of"}:
            raise ValueError("Decision proposal fields must be exact")
        tid = entry["topic_id"]
        d = entry["disposition"]
        if (not isinstance(tid, str) or not ID.fullmatch(tid)
                or tid not in topics or tid in seen or d not in DISPOSITIONS
                or not isinstance(entry["rationale"], str)
                or not 15 <= len(entry["rationale"].strip()) <= 1200
                or not isinstance(entry["answer"], str)
                or len(entry["answer"]) > 1800
                or not isinstance(entry["evidence"], list)
                or len(entry["evidence"]) > 12):
            raise ValueError("Invalid or duplicate proposed disposition")
        seen[tid] = entry
        used = set()
        for source in entry["evidence"]:
            if not isinstance(source, dict) or set(source) != {"source_id", "quote"}:
                raise ValueError("Malformed source claim")
            ref, quote = source["source_id"], source["quote"]
            if not isinstance(ref, str) or ref in used:
                raise ValueError("Unknown or repeated source ID")
            used.add(ref)
            item = github_sources.get(ref) or historical_sources.get(ref)
            if (item is None or not isinstance(quote, str)
                    or not 12 <= len(quote) <= 300
                    or quote not in item["excerpt"]):
                raise ValueError("Evidence quote not present in pinned source excerpt")
        target = entry["duplicate_of"]
        if d == "ANSWERED_BY_GITHUB_EVIDENCE":
            if (not entry["answer"].strip() or target is not None
                    or not entry["evidence"]
                    or not any(s["source_id"] in github_sources
                               and github_sources[s["source_id"]]["source_kind"]
                               in ("CODE", "TEST", "DOCUMENT")
                               for s in entry["evidence"])):
                raise ValueError("Factual resolution requires current GitHub code/docs")
        elif d == "DUPLICATE_OF":
            if (not isinstance(target, str) or target not in topics or target == tid
                    or entry["answer"].strip() or entry["evidence"]):
                raise ValueError("Duplicate must reference another real topic only")
        elif target is not None or entry["answer"].strip():
            raise ValueError("Unresolved question must not assert answer or duplicate")
    # Duplicate references must terminate in an original/decision topic, not
    # an unreviewed chain or circular reference.
    for tid, entry in seen.items():
        if entry["disposition"] == "DUPLICATE_OF":
            target = seen.get(entry["duplicate_of"])
            if target is None or target["disposition"] == "DUPLICATE_OF":
                raise ValueError("Duplicate target must have an explicit primary disposition")
    return seen


def prepare_gate(story, policy, evidence, report, preview, raw_hashes,
                 *, history=None, proposals=None):
    replay_preview(story, policy, evidence, report, preview, raw_hashes)
    historical_sources = validate_history(history, story, policy)
    github_sources = {s["id"]: s for s in evidence["sources"]}
    chosen = validate_proposals(proposals, preview, github_sources, historical_sources)
    items = []
    counts = {}
    for topic in preview["question_topics"]:
        tid = topic["topic_id"]
        proposed = chosen.get(tid)
        d = proposed["disposition"] if proposed else "NOT_YET_RESEARCHED"
        counts[d] = counts.get(d, 0) + 1
        items.append({
            "topic_id": tid,
            "question": topic["question"],
            "original_question_ids": topic["original_question_ids"],
            "proposed_by": topic["proposed_by"],
            "source_ids": topic["source_ids"],
            "proposed_disposition": d,
            "rationale": proposed["rationale"] if proposed else
                         "No validated research disposition was provided.",
            "proposed_answer": proposed["answer"] if proposed else "",
            "supporting_evidence": proposed["evidence"] if proposed else [],
            "duplicate_of": proposed["duplicate_of"] if proposed else None,
            "resolution_verified": False,
            "acceptance_authority": False,
        })
    return {
        "schema_version": 1,
        "kind": "clarity-question-relevance-candidates",
        "target_issue": preview["target_issue"],
        "review_scope": preview["review_scope"],
        "review_report_sha256": preview["review_report_sha256"],
        "github_evidence_sha256": preview["evidence_sha256"],
        "history_sha256": digest(canonical(history).encode()) if history else None,
        "proposals_sha256": digest(canonical(proposals).encode()) if proposals else None,
        "source_status": preview["source_status"],
        "review_gate_status": preview["review_gate_status"],
        "counts": counts,
        "topics": items,
        "proposed_owner_question_ids": [
            x["topic_id"] for x in items
            if x["proposed_disposition"] == "NEEDS_OWNER_DECISION"
        ],
        "outstanding_research_ids": [
            x["topic_id"] for x in items
            if x["proposed_disposition"] in (
                "NOT_YET_RESEARCHED", "NEEDS_TECHNICAL_VERIFICATION")
        ],
        "requires_independent_evidence_verification": True,
        "requires_current_github_recheck": True,
        "automatic_question_suppression_authority": False,
        "inbox_import_authority": False,
        "approval_authority": False,
        "forge_dispatch_authority": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--github-evidence", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--preview", type=Path, required=True)
    parser.add_argument("--linear-history", type=Path)
    parser.add_argument("--proposals", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        story = read_private_report(args.story)
        policy = read_private_report(args.policy)
        evidence = read_private_report(args.github_evidence)
        report = read_private_report(args.review)
        preview = read_private_report(args.preview)
        history = read_private_report(args.linear_history) if args.linear_history else None
        proposals = read_private_report(args.proposals) if args.proposals else None
        data = prepare_gate(
            story, policy, evidence, report, preview,
            (sha_file(args.story), sha_file(args.policy),
             sha_file(args.github_evidence)),
            history=history, proposals=proposals)
        write_private_report(args.output, data)
        print("Question relevance candidates:", len(data["topics"]))
        print("Owner decision candidates:", len(data["proposed_owner_question_ids"]))
        print("Unresolved research:", len(data["outstanding_research_ids"]))
        print("No question suppression, Inbox import, approval or Forge dispatch.")
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        print("BLOCKED: question relevance input validation failed", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
