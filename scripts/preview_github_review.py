"""Offline GitHub evidence -> independent review/question triage preview.

No network, models, tracker writes, inbox imports, approvals or Forge dispatch.
A collected packet alone does NOT mean that a review ran or that unanswered
questions can be inferred. This tool can optionally inspect a private,
already completed review report, retaining reviewer question provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from evidence_context import canonical, validate_evidence_packet
from export_review_questions import extract_proposals, read_private_report
from quality_review import verify_inputs, write_private_report

SOURCE_REF = re.compile(r"(?<![A-Za-z0-9])S-[0-9]{3}(?![A-Za-z0-9])")
WORD = re.compile(r"[a-z0-9]+")
MAX_TOPICS = 150


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalized(text):
    """Conservative exact-meaning punctuation/space normalization only."""
    return re.sub(r"[?.! ]+$", "", " ".join(text.casefold().split()))


def tokens(text):
    return frozenset(WORD.findall(text.casefold()))


def similar_candidates(groups):
    """Suggest possible overlap; never automatically merge different wording."""
    pairs = []
    for i, left in enumerate(groups):
        left_words = tokens(left["question"])
        for right in groups[i + 1:]:
            right_words = tokens(right["question"])
            if not left_words or not right_words:
                continue
            left_nums = {x for x in left_words if x.isdigit()}
            right_nums = {x for x in right_words if x.isdigit()}
            if left_nums != right_nums:
                continue
            flags = {"not", "no", "never", "without", "must", "may", "optional"}
            if left_words.intersection(flags) != right_words.intersection(flags):
                continue
            score = len(left_words & right_words) / len(left_words | right_words)
            if score >= 0.85:
                pairs.append({"left_id": left["topic_id"],
                              "right_id": right["topic_id"],
                              "overlap": round(score, 3),
                              "decision": "HUMAN_REVIEW_ONLY"})
    return pairs[:150]


def prepare(story, policy, evidence, *, report=None, story_file_sha=None,
            policy_file_sha=None, evidence_file_sha=None):
    # A collected issue may have only a synthetic/draft policy (as in the
    # first R720 smoke test). Permit a *non-authoritative* evidence preview,
    # but never treat that as a reviewable source or accept reviewer output.
    try:
        verify_inputs(story, policy)
        policy_contract_valid = True
    except ValueError:
        policy_contract_valid = False
    validate_evidence_packet(evidence, story, policy)
    if evidence["schema_version"] not in (2, 3):
        raise ValueError("Only current GitHub-only v2/v3 evidence is actionable")
    sources = {
        s["id"]: {"id": s["id"], "url": s["url"], "revision": s["revision"],
                  "source_kind": s["source_kind"], "scope": s["scope"]}
        for s in evidence["sources"]
    }
    base = {
        "schema_version": 1,
        "kind": "clarity-github-question-triage-preview",
        "target_issue": evidence["target_issue"],
        "review_scope": evidence["review_scope"],
        "story_sha256": evidence["story_sha256"],
        "policy_sha256": evidence["policy_sha256"],
        "evidence_sha256": hashlib.sha256(canonical(evidence).encode()).hexdigest(),
        "source_status": evidence["freshness"],
        "policy_adopted_claim": policy.get("adopted") is True,
        "risk_register_status_claim": policy.get("risk_register_status", "UNKNOWN"),
        "policy_review_contract": "VALID" if policy_contract_valid else "NOT_READY",
        "sources": list(sources.values()),
        "review_status": "NOT_RUN",
        "question_topics": [],
        "possible_duplicates": [],
        "original_question_count": 0,
        "topic_count": 0,
        "requires_authenticated_owner_review": True,
        "source_authority_verified": False,
        "reviewer_session_authority_verified": False,
        "approval_authority": False,
        "forge_dispatch_authority": False,
        "inbox_import_authority": False,
    }
    if report is None:
        base["next_action"] = (
            "Draft policy must pass scoped-decision validation before an independently "
            "authorized Clarity review; changed evidence must first be recollected.")
        return base
    if not policy_contract_valid:
        raise ValueError("Completed review cannot be attached to incomplete draft policy")
    if evidence["freshness"] == "SOURCE_CHANGED":
        raise ValueError("Changed GitHub source cannot be attached to review triage")
    if not all(isinstance(x, str) and re.fullmatch(r"[0-9a-f]{64}", x)
               for x in (story_file_sha, policy_file_sha, evidence_file_sha)):
        raise ValueError("Review attachment requires exact raw input digests")
    if (report.get("input_file_sha256") != story_file_sha
            or report.get("policy_file_sha256") != policy_file_sha
            or report.get("evidence_file_sha256") != evidence_file_sha):
        raise ValueError("Review report is not bound to the exact private inputs")
    private_batch, _ = extract_proposals(report)  # stage receipts + IDs checked
    all_questions = private_batch["questions"]
    if len(all_questions) > MAX_TOPICS:
        raise ValueError("Exceeded bounded proposed question count")
    grouped = {}
    for item in all_questions:
        key = normalized(item["question"])
        if not key:
            raise ValueError("Empty normalized reviewer question")
        cited = sorted(set(SOURCE_REF.findall(item["question"])))
        unknown = [ref for ref in cited if ref not in sources]
        if unknown:
            raise ValueError("Reviewer question uses unknown source citation")
        if key not in grouped:
            grouped[key] = {
                "topic_id": "topic-" + hashlib.sha256(
                    (private_batch["batch_id"] + ":" + key).encode()
                ).hexdigest()[:20],
                "question": item["question"],
                "original_question_ids": [],
                "proposed_by": [],
                "source_ids": [],
                "source_citation_status": "NOT_CITED",
                "status": "PROPOSED_NEEDS_OWNER_TRIAGE",
                "resolution_authority": False,
                "reason": "Reviewer question needs verification against current project policy.",
            }
        group = grouped[key]
        group["original_question_ids"].append(item["question_id"])
        group["proposed_by"] = sorted(set(group["proposed_by"] + item["proposed_by"]))
        group["source_ids"] = sorted(set(group["source_ids"] + cited))
        group["source_citation_status"] = (
            "EXPLICITLY_CITED" if group["source_ids"] else "NOT_CITED")
    topics = sorted(grouped.values(), key=lambda q: q["topic_id"])
    base.update({
        "review_status": "REVIEW_QUESTIONS_PROPOSED" if topics else "REVIEW_NO_QUESTIONS",
        "review_gate_status": private_batch["review_gate_status"],
        "review_report_sha256": private_batch["report_sha256"],
        "review_batch_id": private_batch["batch_id"],
        "original_question_count": len(all_questions),
        "topic_count": len(topics),
        "question_topics": topics,
        "possible_duplicates": similar_candidates(topics),
        "next_action": "Human inspection of sources and reviewer questions; no automatic inbox import.",
    })
    return base


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--report", type=Path, help="Optional already completed private Clarity review")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        story = read_private_report(args.story)
        policy = read_private_report(args.policy)
        evidence = read_private_report(args.evidence)
        report = read_private_report(args.report) if args.report else None
        output = prepare(
            story, policy, evidence, report=report,
            story_file_sha=file_sha(args.story) if report else None,
            policy_file_sha=file_sha(args.policy) if report else None,
            evidence_file_sha=file_sha(args.evidence) if report else None)
        write_private_report(args.output, output)
        print("GitHub triage preview:", output["target_issue"])
        print("Sources:", len(output["sources"]), "review:", output["review_status"],
              "topics:", output["topic_count"])
        print("No model, tracker write, Inbox import, approval or Forge dispatch.")
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        print("BLOCKED: private GitHub review triage validation failed", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
