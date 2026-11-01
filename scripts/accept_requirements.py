#!/usr/bin/env python3
"""Read-only, zero-authority Clarity requirement acceptance proposal validator.

Never authenticates people, policy adoption, source revision or real model sessions.
Never returns ACCEPTED, writes a tracker or grants Forge execution permissions.
The verified trust-bound acceptance ledger belongs in a separate supervisor.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import sys
import zipfile

from export_forge_handoff import validate_criteria, _feature_tags

HEX = re.compile(r"[0-9a-f]{64}\Z")
AC = re.compile(r"AC-[A-Za-z0-9_.-]+\Z")
KINDS = {"linear", "jira", "github", "local"}
STAGES = ("investigator", "evaluator", "challenger")
DIMENSIONS = {f"D{x}" for x in range(1, 11)}
CHECKS = {f"L{x}" for x in range(1, 11)}
MAX_INPUT = 300_000
MAX_ZIP = 2_000_000


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("utf-8")


def ensure(cond, error):
    if not cond:
        raise ValueError(error)


def read(path: Path, limit=MAX_INPUT) -> bytes:
    path = path.absolute()
    ensure(not any(p.is_symlink() for p in (path, *path.parents)), "Symlink source not permitted")
    ensure(path.is_file() and stat.S_ISREG(path.stat().st_mode), "Input must be regular file")
    ensure(0 < path.stat().st_size <= limit, "Invalid input size")
    return path.read_bytes()


def parse(data: bytes):
    def pairs(items):
        result = {}
        for k, v in items:
            ensure(k not in result, "Duplicate JSON key")
            result[k] = v
        return result
    return json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite number")))


def sha_valid(value):
    return isinstance(value, str) and HEX.fullmatch(value) is not None


def inspect_handoff(raw: bytes, story: dict, system: str, ref: str, revision: str):
    ensure(len(raw) <= MAX_ZIP, "ZIP too large")
    with zipfile.ZipFile(io.BytesIO(raw), "r") as z:
        infos = z.infolist()
        names = [entry.filename for entry in infos]
        basic = {"requirement.md", "criteria.json", "handoff.json"}
        ensure(set(names) in (basic, basic | {"acceptance.feature"}), "Invalid handoff file set")
        ensure(len(names) == len(set(names)), "Duplicate ZIP filenames")
        ensure(all("/" not in n and "\\" not in n and ".." not in n for n in names),
               "Nested or unsafe ZIP entry")
        ensure(all(not entry.is_dir() and (entry.external_attr >> 16 & 0o170000) != 0o120000
                   and entry.file_size <= 1_000_000 for entry in infos),
               "Unsupported ZIP file type or size")
        ensure(sum(entry.file_size for entry in infos) < 2_000_000, "Oversized expanded ZIP")
        files = {n: z.read(n) for n in names}

    meta = parse(files["handoff.json"])
    ensure(isinstance(meta, dict) and set(meta) == {
        "schema_version", "kind", "run_id", "revision", "story_type", "source",
        "criterion_ids", "files"
    }, "Unexpected handoff metadata")
    ensure(type(meta["schema_version"]) is int and meta["schema_version"] == 2
           and meta["kind"] == "clarity-portable-handoff", "Unsupported handoff")
    ensure(type(meta["revision"]) is int and meta["revision"] > 0
           and str(meta["revision"]) == revision, "Handoff revision differs from source")
    ensure(meta["source"] == {"system": system, "ref": ref}, "Handoff source identity mismatch")
    ensure(meta["story_type"] == story.get("story_type"), "Handoff story type mismatch")
    ensure(isinstance(meta["files"], dict) and set(meta["files"]) == set(files)-{"handoff.json"},
           "Handoff digest index differs")
    for name, digest in meta["files"].items():
        ensure(sha_valid(digest) and sha(files[name]) == digest,
               "Handoff file digest mismatch: " + name)

    _, ids = validate_criteria(files["criteria.json"], "acceptance.feature" in files)
    ensure(isinstance(meta["criterion_ids"], list) and meta["criterion_ids"] == ids,
           "Handoff criterion identity/order differs")
    ensure(all(isinstance(i, str) and AC.fullmatch(i) for i in ids),
           "Acceptance proposal needs stable AC- identifiers")
    ensure(isinstance(story.get("payload"), str) and
           files["requirement.md"] == story["payload"].encode("utf-8"),
           "Reviewed requirement differs from exported requirement.md")
    if story["story_type"] == "behavioral":
        ensure(isinstance(story.get("feature"), str)
               and files["acceptance.feature"] == story["feature"].encode("utf-8"),
               "Reviewed feature differs from exported Gherkin")
        ensure(_feature_tags(files["acceptance.feature"]) == ids,
               "Gherkin scenario IDs do not match criteria")
    else:
        ensure(isinstance(story.get("criteria"), list), "Missing reviewed criteria list")
        actual = parse(files["criteria.json"])["criteria"]
        ensure(len(actual) == len(story["criteria"]) and
               [entry["text"] for entry in actual] == story["criteria"],
               "Exported acceptance criteria differ from reviewed criteria")
    return ids


def assess(*, story_data: bytes, current_data: bytes, review_data: bytes,
           review_policy_data: bytes, acceptance_policy_data: bytes,
           zip_data: bytes, system: str, ref: str, revision: str):
    # All inputs are operator-supplied snapshots. Compare bytes; no network
    # identity or authority is inferred from their contents.
    ensure(system in KINDS and isinstance(ref, str) and 0 < len(ref) <= 120
           and re.fullmatch(r"[A-Za-z0-9_.-]+", ref),
           "Invalid source system/reference")
    ensure(isinstance(revision, str) and revision.isdigit() and int(revision) > 0,
           "Invalid revision")
    story = parse(story_data)
    ensure(isinstance(story, dict), "Story must be a JSON object")
    ids = inspect_handoff(zip_data, story, system, ref, revision)
    review = parse(review_data)
    project_review_policy = parse(review_policy_data)
    accept_policy = parse(acceptance_policy_data)
    ensure(isinstance(review, dict) and isinstance(accept_policy, dict)
           and isinstance(project_review_policy, dict), "Invalid review/policy structure")
    ensure(isinstance(accept_policy.get("project"), str)
           and accept_policy["project"].strip(), "Acceptance policy project missing")
    ensure(isinstance(accept_policy.get("id"), str) and accept_policy["id"].strip()
           and isinstance(accept_policy.get("revision"), str)
           and accept_policy["revision"].strip(), "Acceptance policy identifier/revision missing")
    reasons = []
    def block(s):
        if s not in reasons:
            reasons.append(s)

    if story_data != current_data:
        block("FROZEN_SOURCE_DIFFERS_FROM_SUPPLIED_CURRENT_SNAPSHOT")

    if review.get("schema_version") != 1 or review.get("kind") != "clarity-independent-review":
        block("INVALID_REVIEW_ENVELOPE")
    if review.get("input_file_sha256") != sha(story_data):
        block("REVIEW_STORY_DIGEST_MISMATCH")
    if review.get("policy_file_sha256") != sha(review_policy_data):
        block("REVIEW_POLICY_DIGEST_MISMATCH")
    if review.get("pilot_with_draft_policy") is not False:
        block("PILOT_OR_UNVERIFIED_POLICY_REVIEW")
    lint = review.get("deterministic")
    if not isinstance(lint, dict) or lint.get("kind") != "clarity-deterministic-quality-report":
        block("DETERMINISTIC_REPORT_MISSING")
    else:
        if lint.get("status") != "PASS" or lint.get("open_question_count") != 0:
            block("DETERMINISTIC_NOT_CLEAN")
        checks = lint.get("checks")
        if not isinstance(checks, dict) or set(checks) != CHECKS:
            block("DETERMINISTIC_CHECK_COVERAGE_MISSING")
        elif any(not isinstance(v, dict) or v.get("status") not in
                 ("PASS", "NOT_APPLICABLE") for v in checks.values()):
            block("DETERMINISTIC_UNRESOLVED_CHECK")
        # NOT_APPLICABLE applies to nonbehavioral Gherkin checks; review still
        # must prove context-specific semantic applicability, not ignore it.
        if lint.get("ready_for_handover") is not False:
            block("DETERMINISTIC_AUTHORITY_VIOLATION")

    run = review.get("run")
    if not isinstance(run, dict) or not isinstance(run.get("aggregate"), dict):
        block("SEMANTIC_RUN_MISSING")
    else:
        if run["aggregate"].get("status") != "REVIEWABLE_CANDIDATE" or \
                run["aggregate"].get("ready_for_handover") is not False or \
                run["aggregate"].get("publication_authority") is not False:
            block("SEMANTIC_REVIEW_NOT_CLEAN")
        results, receipts = run.get("results"), run.get("receipts")
        if not isinstance(results, dict) or set(results) != set(STAGES) or \
                not isinstance(receipts, dict) or set(receipts) != set(STAGES):
            block("INDEPENDENT_STAGES_MISSING")
        else:
            run_ids, sessions = set(), set()
            story_hash = sha(canonical(story))
            policy_hash = sha(canonical(project_review_policy))
            for stage in STAGES:
                outcome, receipt = results[stage], receipts[stage]
                if not isinstance(outcome, dict) or not isinstance(receipt, dict):
                    block("INVALID_SEMANTIC_STAGE")
                    continue
                if outcome.get("stage") != stage or outcome.get("verdict") != "PASS" \
                   or outcome.get("questions") or outcome.get("findings"):
                    block("UNRESOLVED_SEMANTIC_FINDINGS")
                if stage == "evaluator":
                    dims = outcome.get("dimensions")
                    if not isinstance(dims, list) or len(dims) != 10 or \
                       {d.get("id") for d in dims if isinstance(d, dict)} != DIMENSIONS or \
                       any(not isinstance(d, dict) or d.get("status") != "PASS" or
                           not d.get("evidence") or not d.get("rationale") for d in dims):
                        block("SEMANTIC_DIMENSIONS_NOT_CLEAN")
                elif outcome.get("dimensions") != []:
                    block("UNEXPECTED_STAGE_DIMENSIONS")
                if receipt.get("backend") != "claude-code" or receipt.get("synthetic") is True or \
                   not isinstance(receipt.get("session_id"), str) or not receipt["session_id"]:
                    block("UNVERIFIED_REVIEW_BACKEND")
                if receipt.get("input_sha256") != story_hash or receipt.get("policy_sha256") != policy_hash:
                    block("REVIEW_RECEIPT_INPUT_MISMATCH")
                rid = receipt.get("run_id")
                sid = receipt.get("session_id")
                if not isinstance(rid, str) or not rid or rid in run_ids or sid in sessions:
                    block("NONINDEPENDENT_REVIEW_RECEIPTS")
                run_ids.add(rid)
                sessions.add(sid)

    if project_review_policy.get("adopted") is not True or \
       project_review_policy.get("risk_register_status") != "APPROVED":
        block("REVIEW_POLICY_NOT_APPROVED")
    # No uploaded policy can establish who approved it. Only the future
    # authenticated supervisor can verify this claim, even if status APPROVED.
    approved_claim = (
        accept_policy.get("status") == "APPROVED" and
        isinstance(accept_policy.get("approval"), dict) and
        accept_policy["approval"].get("do_r_and_risk_policy_ratified") is True
    )
    if not approved_claim:
        policy_result = "NEEDS_DECISION"
        if "ACCEPTANCE_POLICY_UNRATIFIED" not in reasons:
            reasons.append("ACCEPTANCE_POLICY_UNRATIFIED")
    else:
        policy_result = "CANDIDATE"
    # No authenticated source-adapter or signer exists in this tool.
    if reasons:
        status = "BLOCKED" if any(x not in {"ACCEPTANCE_POLICY_UNRATIFIED"} for x in reasons) \
                 else "NEEDS_DECISION"
    else:
        status = policy_result
    ensure(len(reasons) <= 50, "Too many blocker codes")
    return {
        "schema_version": 1,
        "kind": "clarity-requirement-acceptance-proposal",
        "source": {"system": system, "ref": ref, "revision": revision,
                   "content_sha256": sha(story_data)},
        "handoff_sha256": sha(zip_data),
        "criterion_ids": ids,
        "quality_report_sha256": sha(review_data),
        "project_policy": {"id": accept_policy["id"],
                           "revision": accept_policy["revision"],
                           "sha256": sha(acceptance_policy_data)},
        "result": status,
        "reasons": reasons
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ("story", "current-story", "review", "review-policy", "acceptance-policy",
                 "handoff", "output"):
        p.add_argument("--" + flag, required=True, type=Path)
    p.add_argument("--source-system", choices=sorted(KINDS), required=True)
    p.add_argument("--source-ref", required=True)
    p.add_argument("--revision", required=True)
    a = p.parse_args()
    try:
        payload = assess(
            story_data=read(a.story), current_data=read(a.current_story),
            review_data=read(a.review), review_policy_data=read(a.review_policy),
            acceptance_policy_data=read(a.acceptance_policy),
            zip_data=read(a.handoff, MAX_ZIP),
            system=a.source_system, ref=a.source_ref, revision=a.revision)
        out = a.output.absolute()
        ensure(not any(x.is_symlink() for x in (out, *out.parents)), "Symlink output forbidden")
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
        print("Clarity proposal: " + payload["result"] + " (NO approval/authority)")
        return 0 if payload["result"] == "CANDIDATE" else 3
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile,
            UnicodeError, KeyError, TypeError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
