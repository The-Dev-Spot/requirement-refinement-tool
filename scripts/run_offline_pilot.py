"""Replay a private selected-evidence collection and existing review artifacts.

No provider invocation, HTTP calls, source refresh, issue/Inbox writes,
requirements approval or Forge dispatch. Missing stages remain NOT_RUN.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from evidence_context import canonical, digest, HEX64
from preview_github_review import prepare
from quality_review import write_private_report
from question_freshness_attestation import read_attestation_key
from question_relevance_gate import validate_history
from question_relevance_verify import validate_research
from reconcile_question_evidence import reconcile, validate_challenge
from select_discovery_evidence import FLAGS, load_collection, read_snapshot

STAGES = ("review", "research", "challenge", "freshness")


def replay(story, policy, raw_hashes, collection, collector_key, reports=None, *, history=None, now=None, max_age_seconds=300):
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 900:
        raise ValueError("Trusted freshness age must be within 1..900 seconds")
    values, file_hashes = load_collection(collection, story, policy, collector_key)
    reports = {} if reports is None else reports
    if (not isinstance(reports, dict) or set(reports) - set(STAGES)
            or any(not isinstance(v, dict) for v in reports.values())):
        raise ValueError("Unsupported replay stage")
    present = [s for s in STAGES if s in reports]
    if present != list(STAGES[:len(present)]):
        raise ValueError("Replay artifacts must form an uninterrupted stage prefix")
    if history is not None:
        validate_history(history, story, policy)
    evidence = values["evidence.json"]
    hashes = tuple(raw_hashes) + (file_hashes["evidence.json"],)
    if len(hashes) != 3 or any(not isinstance(h, str) or not HEX64.fullmatch(h) for h in hashes):
        raise ValueError("Exact story/policy file hashes required")
    states = {"collection": "VALIDATED_OFFLINE", **{s: "NOT_RUN" for s in STAGES}}
    preview, candidate, result = None, None, None
    if "review" in reports:
        preview = prepare(story, policy, evidence, report=reports["review"],
                          story_file_sha=hashes[0], policy_file_sha=hashes[1], evidence_file_sha=hashes[2])
        states["review"] = "REPLAYED"
    if "research" in reports:
        candidate = validate_research(story, policy, evidence, reports["review"], preview, hashes,
                                      reports["research"], history=history)
        states["research"] = "REPLAYED"
    if "challenge" in reports:
        validate_challenge(reports["challenge"], reports["research"], evidence, reports["review"], preview, history)
        states["challenge"] = "REPLAYED"
    if "freshness" in reports:
        result = reconcile(story, policy, evidence, reports["review"], preview, hashes,
                           reports["research"], reports["challenge"], reports["freshness"], collector_key,
                           history=history, discussion_snapshot=values["discussion-snapshot.json"],
                           now=now, max_age_seconds=max_age_seconds)
        states["freshness"] = "AUTHENTICATED_MATCH_AT_READ_TIME"
    topics = (result["topics"] if result else candidate["topics"] if candidate else
              preview["question_topics"] if preview else None)
    return {
        "schema_version": 1, "kind": "clarity-offline-pilot-replay", "mode": "REPLAY_ONLY", "status": "BLOCKED",
        "target_issue": story["source_issue_id"], "review_scope": evidence["review_scope"], "stages": states,
        "bindings": {name: digest(canonical(value).encode()) for name, value in (
            ("story", story), ("policy", policy), ("collection_receipt_files", file_hashes),
            ("review_artifacts", reports), ("linear_history", history))},
        "raw_input_sha256": {"story": hashes[0], "policy": hashes[1], "evidence": hashes[2]},
        "selected_candidate_ids": values["selection.json"]["candidate_ids"],
        "topics": topics, "topic_count": len(topics) if topics is not None else None,
        "unresolved_topic_ids": [t["topic_id"] for t in topics] if topics is not None else None,
        "reconciliation": result,
        "block_reasons": ["MISSING_STAGE_" + s.upper() for s in STAGES if s not in reports]
                         + (result["block_reasons"] if result else ["AUTHORITY_AND_CURRENT_FRESHNESS_NOT_VERIFIED"]),
        "model_calls_executed": False, "network_calls_executed": False,
        "linear_history_authority": "HISTORICAL_UNVERIFIED" if history else "NOT_SUPPLIED",
        **{flag: False for flag in FLAGS},
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("story", "policy", "collection-dir", "collector-key-file", "output"):
        p.add_argument("--" + name, required=True, type=Path)
    for name in (*STAGES, "linear-history"):
        p.add_argument("--" + name, type=Path)
    p.add_argument("--max-age-seconds", type=int, default=300)
    args = p.parse_args()
    try:
        story, story_hash = read_snapshot(args.story)
        policy, policy_hash = read_snapshot(args.policy)
        reports = {s: read_snapshot(getattr(args, s))[0] for s in STAGES if getattr(args, s)}
        history = read_snapshot(args.linear_history)[0] if args.linear_history else None
        result = replay(story, policy, (story_hash, policy_hash), args.collection_dir,
                        read_attestation_key(args.collector_key_file), reports, history=history,
                        max_age_seconds=args.max_age_seconds)
        write_private_report(args.output, result)
        print("BLOCKED: offline pilot replay completed; missing stages remain NOT_RUN.")
        return 0
    except (OSError, ValueError, KeyError, TypeError, UnicodeError):
        print("BLOCKED: offline pilot artifact validation failed", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
