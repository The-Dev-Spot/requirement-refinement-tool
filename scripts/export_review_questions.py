"""Export proposed Clarity reviewer questions as private evidence and safe outbox metadata.

This is a read-only, offline bridge. It NEVER sends to Slack, writes a tracker,
approves a requirement, or permits Forge to start. Questions are untrusted
proposals pending canonical source/owner verification by a separate service.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat

from quality_review import write_private_report

STAGES = ("investigator", "evaluator", "challenger")
HEX = re.compile(r"[0-9a-f]{64}\Z")
MAX_REPORT_BYTES = 2_000_000
MAX_PROPOSED_QUESTIONS = 150


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(value: bytes):
    return hashlib.sha256(value).hexdigest()


def read_private_report(path: Path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Report must be an existing regular, non-symlinked file")
    if path.stat().st_size > MAX_REPORT_BYTES or path.stat().st_size < 1:
        raise ValueError("Invalid report size")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("Private review report must not be group/world accessible")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("Malformed review report")
    return report


def extract_proposals(report):
    """Build stable per-report IDs; private questions are not Slack messages."""
    if (report.get("schema_version") != 1
            or report.get("kind") != "clarity-independent-review"):
        raise ValueError("Not a Clarity independent quality review")
    for key in ("input_file_sha256", "policy_file_sha256", "rubric_file_sha256"):
        if not isinstance(report.get(key), str) or not HEX.fullmatch(report[key]):
            raise ValueError("Missing or invalid reviewed " + key)
    run = report.get("run")
    if not isinstance(run, dict):
        raise ValueError("Missing real run payload")
    results, receipts, aggregate = run.get("results"), run.get("receipts"), run.get("aggregate")
    if not isinstance(results, dict) or not isinstance(receipts, dict) or not isinstance(aggregate, dict):
        raise ValueError("Missing reviewer results, receipts or aggregate")
    if aggregate.get("status") not in ("BLOCKED", "FAIL", "REVIEWABLE_CANDIDATE"):
        raise ValueError("Unknown review gate status")

    report_hash = sha(canonical(report).encode())
    batch_id = "clarity-q-" + report_hash[:32]
    combined = {}
    for stage in STAGES:
        if stage not in results:
            continue
        result = results[stage]
        receipt = receipts.get(stage)
        if (not isinstance(result, dict) or not isinstance(receipt, dict)
                or result.get("stage") != stage
                or receipt.get("model_verified") is not True
                or not isinstance(receipt.get("session_id"), str)
                or not receipt["session_id"]):
            raise ValueError("Question stage has no validated model/session receipt")
        questions = result.get("questions")
        if not isinstance(questions, list) or len(questions) > 50:
            raise ValueError("Malformed stage question list")
        for proposed in questions:
            if not isinstance(proposed, str) or not proposed.strip() or len(proposed) > 1800:
                raise ValueError("Invalid proposed question")
            normalized = " ".join(proposed.split())
            identity = normalized.casefold()
            if identity not in combined:
                combined[identity] = {
                    "question_id": "q-" + sha((batch_id + ":" + identity).encode())[:24],
                    "question": normalized,
                    "proposed_by": [],
                    "status": "PROPOSED",
                    "authority": "UNVERIFIED",
                }
            combined[identity]["proposed_by"].append(stage)
    if len(combined) > MAX_PROPOSED_QUESTIONS:
        raise ValueError("Too many proposed questions")

    proposals = sorted(combined.values(), key=lambda item: item["question_id"])
    if proposals:
        disposition = "NEEDS_INFORMATION"
    elif aggregate["status"] == "REVIEWABLE_CANDIDATE":
        disposition = "NO_QUESTIONS"
    else:
        disposition = "REVIEW_BLOCKED_WITHOUT_QUESTIONS"

    private_batch = {
        "schema_version": 1, "kind": "clarity-question-proposals",
        "batch_id": batch_id, "report_sha256": report_hash,
        "reviewed_input_sha256": report["input_file_sha256"],
        "reviewed_policy_sha256": report["policy_file_sha256"],
        "rubric_sha256": report["rubric_file_sha256"],
        "review_gate_status": aggregate["status"],
        "state": disposition, "questions": proposals,
        "tracker_source_revision": None,
        "tracker_authority_verified": False,
        "approval_authority": False, "forge_dispatch_authority": False,
    }

    # This is the ONLY object intended for a notification/outbox bridge.
    # Never include private questions, findings, raw responses, credentials,
    # session IDs, model prompts or private report paths.
    event = {
        "schema_version": 1,
        "event_type": "clarity.question_batch_proposed",
        "event_id": "evt-" + sha((batch_id + ":notify-v1").encode())[:32],
        "batch_id": batch_id,
        "report_sha256": report_hash,
        "reviewed_input_sha256": report["input_file_sha256"],
        "question_count": len(proposals),
        "state": disposition,
        "review_gate_status": aggregate["status"],
        "needs_trusted_source_binding": True,
        "approval_authority": False,
        "forge_dispatch_authority": False,
    }
    return private_batch, event


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--outbox-output", type=Path, required=True)
    args = parser.parse_args()
    if args.private_output.absolute() == args.outbox_output.absolute():
        parser.error("Private and outbox outputs must be separate paths")
    batch, event = extract_proposals(read_private_report(args.report))
    # Exclusive mode 0600 writes. No overwrite on retry (external orchestrator
    # must idempotently reconcile by event_id and batch_id).
    write_private_report(args.private_output, batch)
    write_private_report(args.outbox_output, event)
    print("Question proposals:", event["question_count"], "state:", event["state"])
    print("Outbox event ID:", event["event_id"])
    print("No notification, tracker write, acceptance or Forge dispatch was executed")


if __name__ == "__main__":
    main()
