"""Offline trusted reconciliation of question proposals and collector receipts.

Authenticates source readbacks and replays every model proposal against its
exact inputs. All questions remain unresolved candidates. No tools, network,
inference, Inbox integration, owner approval, or Forge dispatch.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from evidence_context import canonical, digest
from export_review_questions import read_private_report
from quality_review import model_matches, write_private_report
from question_freshness_attestation import read_attestation_key, verify_freshness
from question_relevance_verify import (
    OUTCOMES, build_challenge_prompt, validate_assessments, validate_research,
)

NO_AUTHORITY = (
    "current_source_truth_verified", "semantic_answer_authority_verified",
    "owner_decision_authority_verified", "automatic_question_suppression_authority",
    "inbox_import_authority", "approval_authority", "forge_dispatch_authority",
)
READBACK_FALSE = (
    "owner_policy_authority_verified", "semantic_answer_sufficiency_verified",
    "automatic_question_suppression_authority", "inbox_import_authority",
    "approval_authority", "forge_dispatch_authority",
)


def validate_challenge(challenge, research, evidence, report, preview, history):
    expected = {
        "schema_version", "kind", "target_issue", "review_report_sha256",
        "source_evidence_sha256", "research_proposal_sha256", "model_receipt",
        "assessments", "counts", "independent_model_challenge_completed",
        *NO_AUTHORITY,
    }
    if (not isinstance(challenge, dict) or set(challenge) != expected
            or type(challenge["schema_version"]) is not int
            or challenge["schema_version"] != 1
            or challenge["kind"] != "clarity-independent-question-challenge"
            or challenge["target_issue"] != preview["target_issue"]
            or challenge["review_report_sha256"] != preview["review_report_sha256"]
            or challenge["source_evidence_sha256"] != preview["evidence_sha256"]
            or challenge["research_proposal_sha256"] != digest(canonical(research).encode())
            or challenge["independent_model_challenge_completed"] is not True
            or any(challenge[x] is not False for x in NO_AUTHORITY)):
        raise ValueError("Independent challenge identity or authority mismatch")
    receipt = challenge["model_receipt"]
    prompt = build_challenge_prompt(preview, evidence, research, history)
    if (not isinstance(receipt, dict)
            or receipt.get("provider") != "claude-code"
            or receipt.get("model_verified") is not True
            or not isinstance(receipt.get("model_requested"), str)
            or not receipt["model_requested"]
            or not isinstance(receipt.get("model_resolved"), str)
            or not model_matches(receipt["model_requested"], receipt["model_resolved"])
            or not isinstance(receipt.get("session_id"), str)
            or not receipt["session_id"].strip()
            or type(receipt.get("question_count")) is not int
            or receipt["question_count"] != len(research["batch_topic_ids"])
            or receipt.get("prompt_sha256") != digest(prompt.encode())):
        raise ValueError("Independent challenge receipt differs from exact prompt")
    sessions = {r.get("session_id") for r in report["run"]["receipts"].values()
                if isinstance(r, dict)}
    sessions.add(research["receipt"]["session_id"])
    if receipt["session_id"] in sessions:
        raise ValueError("Independent challenge reused an earlier session")
    assessments = validate_assessments(challenge["assessments"], research, evidence, history)
    counts = {o: sum(a["outcome"] == o for a in assessments) for o in OUTCOMES}
    if (not isinstance(challenge["counts"], dict)
            or any(type(v) is not int for v in challenge["counts"].values())
            or challenge["counts"] != counts):
        raise ValueError("Independent challenge counts differ")
    return {a["topic_id"]: a for a in assessments}


def validate_readback(readback, evidence):
    expected = {
        "schema_version", "kind", "target_issue", "review_scope", "evidence_sha256",
        "story_sha256", "policy_sha256", "recheck_status", "rechecked_sources",
        "github_network_rechecked", *READBACK_FALSE,
    }
    if (not isinstance(readback, dict) or set(readback) != expected
            or type(readback["schema_version"]) is not int or readback["schema_version"] != 1
            or readback["kind"] != "clarity-github-source-freshness-recheck"
            or readback["target_issue"] != evidence["target_issue"]
            or readback["review_scope"] != evidence["review_scope"]
            or readback["evidence_sha256"] != digest(canonical(evidence).encode())
            or readback["story_sha256"] != evidence["story_sha256"]
            or readback["policy_sha256"] != evidence["policy_sha256"]
            or readback["github_network_rechecked"] is not True
            or readback["recheck_status"] != "MATCHED_AT_READ_TIME"
            or any(readback[x] is not False for x in READBACK_FALSE)):
        raise ValueError("Collector did not establish matching source readback")
    expected_sources = [{
        "source_id": s["id"], "source_kind": s["source_kind"],
        "claimed_revision": s["revision"], "observed_revision": s["revision"],
        "content_matches": True, "status": "MATCHED",
    } for s in evidence["sources"]]
    if canonical(readback["rechecked_sources"]) != canonical(expected_sources):
        raise ValueError("Readback must cover every exact source once")
    # Do not let other scoped sources or an absent target establish current context.
    repo, number = evidence["target_issue"].split("#")
    target_url = "https://github.com/%s/issues/%s" % (repo, number)
    if (sum(s["source_kind"] == "ISSUE" and s["url"] == target_url
            for s in evidence["sources"]) != 1
            or any(s["scope"] != evidence["review_scope"] for s in evidence["sources"])):
        raise ValueError("Source scope or target issue coverage mismatch")


def reconcile(story, policy, evidence, report, preview, hashes, research,
              challenge, freshness, collector_key, *, history=None,
              now=None, max_age_seconds=300):
    candidate = validate_research(story, policy, evidence, report, preview, hashes,
                                  research, history=history)
    assessments = validate_challenge(challenge, research, evidence, report, preview, history)
    readback = verify_freshness(freshness, challenge, collector_key,
                               now=now, max_age_seconds=max_age_seconds)
    validate_readback(readback, evidence)
    topics = []
    for original in candidate["topics"]:
        item = dict(original)
        a = assessments.get(item["topic_id"])
        state = "NOT_YET_RESEARCHED"
        if a:
            state = {"DISPUTE": "DISPUTED", "INSUFFICIENT_EVIDENCE": "NEEDS_RESEARCH"}.get(a["outcome"])
            if state is None:
                state = {
                    "ANSWERED_BY_GITHUB_EVIDENCE": "SUPPORTED_ANSWER_CANDIDATE",
                    "NEEDS_OWNER_DECISION": "OWNER_DECISION_CANDIDATE",
                    "NEEDS_TECHNICAL_VERIFICATION": "NEEDS_TECHNICAL_VERIFICATION",
                    "DUPLICATE_OF": "DUPLICATE_CANDIDATE",
                }[item["proposed_disposition"]]
        item.update(reconciliation_status=state, independent_assessment=a,
                    resolution_verified=False, acceptance_authority=False)
        topics.append(item)
    # A duplicate remains visible even if its primary is disputed/unresearched.
    index = {t["topic_id"]: t for t in topics}
    for item in topics:
        item["duplicate_primary_status"] = (
            index[item["duplicate_of"]]["reconciliation_status"]
            if item["duplicate_of"] else None)
    return {
        "schema_version": 1, "kind": "clarity-question-evidence-reconciliation",
        "target_issue": preview["target_issue"], "review_scope": preview["review_scope"],
        "status": "BLOCKED", "source_status": "AUTHENTICATED_MATCH_AT_READ_TIME",
        "bindings": {name: digest(canonical(value).encode()) for name, value in (
            ("story", story), ("policy", policy), ("evidence", evidence), ("review", report),
            ("preview", preview), ("research", research), ("challenge", challenge),
            ("freshness", freshness), ("linear_history", history))},
        "source_read_started_at": freshness["payload"]["started_at"],
        "source_read_completed_at": freshness["payload"]["completed_at"],
        "source_receipt_max_age_seconds": max_age_seconds,
        "topics": topics,
        "counts": {state: sum(t["reconciliation_status"] == state for t in topics)
                   for state in sorted({t["reconciliation_status"] for t in topics})},
        "unresolved_topic_ids": [t["topic_id"] for t in topics],
        "owner_question_candidate_ids": [t["topic_id"] for t in topics
                                         if t["reconciliation_status"] == "OWNER_DECISION_CANDIDATE"],
        "linear_history_authority": "HISTORICAL_UNVERIFIED" if history else "NOT_SUPPLIED",
        "block_reasons": ["SEMANTIC_AND_MATERIALITY_AUTHORITY_NOT_VERIFIED",
                          "CURRENT_OWNER_POLICY_AUTHORITY_NOT_VERIFIED",
                          "PROTECTED_INBOX_ADAPTER_NOT_AUTHORIZED",
                          "APPROVAL_AND_FORGE_DISPATCH_BLOCKED"],
        **{flag: False for flag in NO_AUTHORITY},
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("story", "policy", "github-evidence", "review", "preview", "research",
                 "challenge", "freshness", "collector-key-file", "output"):
        p.add_argument("--" + name, required=True, type=Path)
    p.add_argument("--linear-history", type=Path)
    p.add_argument("--max-age-seconds", type=int, default=300)
    args = p.parse_args()
    try:
        paths = [args.story, args.policy, args.github_evidence, args.review,
                 args.preview, args.research, args.challenge, args.freshness]
        # Existing preview contracts bind source file bytes as well as content.
        inputs = [read_private_report(path) for path in paths]
        hashes = tuple(digest(path.read_bytes()) for path in paths[:3])
        history = read_private_report(args.linear_history) if args.linear_history else None
        result = reconcile(*inputs[:5], hashes, *inputs[5:],
                           read_attestation_key(args.collector_key_file), history=history,
                           max_age_seconds=args.max_age_seconds)
        write_private_report(args.output, result)
        print("BLOCKED: reconciled %d unresolved question topics; no approval or Forge dispatch."
              % len(result["topics"]))
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        print("BLOCKED: question evidence reconciliation failed validation", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
