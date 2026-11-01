#!/usr/bin/env python3
"""Replay multiple Clarity review packets against one frozen gold case.

A QA benchmark, not a model session launcher, trusted attestation or acceptance
authority. It accepts results from ChatGPT, Claude/Opus or another provider in
Clarity's existing stage schema. Deterministic rules and gold case are shared.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from quality_review import STAGES, check_stage, summarize

MAX_SOURCE = 300_000


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse(path: Path):
    data = path.read_bytes()
    if not (0 < len(data) <= MAX_SOURCE) or path.is_symlink():
        raise ValueError("Missing, oversized or symlinked input")
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("Duplicate JSON key")
            out[key] = value
        return out
    return json.loads(data, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON"))), digest(data)


def validate_gold(gold, source: str, source_sha: str, policy_sha: str):
    if not isinstance(gold, dict) or set(gold) != {
        "schema_version", "case_id", "source_sha256", "policy_sha256",
        "expected_aggregate", "required_findings", "source_anchors"
    }:
        raise ValueError("Invalid or incomplete gold-case fields")
    if type(gold["schema_version"]) is not int or gold["schema_version"] != 1:
        raise ValueError("Unsupported gold-case schema")
    if not isinstance(gold["case_id"], str) or not gold["case_id"].strip():
        raise ValueError("Missing benchmark case ID")
    if gold["source_sha256"] != source_sha or gold["policy_sha256"] != policy_sha:
        raise ValueError("Gold case is not bound to exact source and policy bytes")
    if gold["expected_aggregate"] not in ("BLOCKED", "REVIEWABLE_CANDIDATE"):
        raise ValueError("Invalid expected outcome")
    if not isinstance(gold["source_anchors"], list) or not gold["source_anchors"]:
        raise ValueError("Gold case needs independent source anchors")
    for quote in gold["source_anchors"]:
        if not isinstance(quote, str) or len(quote) < 8 or quote not in source:
            raise ValueError("Gold source anchor missing from frozen source")
    if not isinstance(gold["required_findings"], list):
        raise ValueError("Invalid gold findings")
    if gold["expected_aggregate"] == "BLOCKED" and not gold["required_findings"]:
        raise ValueError("Blocked gold case must explain expected failures")
    for f in gold["required_findings"]:
        if not isinstance(f, dict) or set(f) != {"id", "aliases", "required_stages"}:
            raise ValueError("Gold finding must have id, aliases and required stages")
        if not isinstance(f["id"], str) or not f["id"].strip():
            raise ValueError("Invalid finding ID")
        if not isinstance(f["aliases"], list) or not f["aliases"] or any(
            not isinstance(p, str) or not (2 <= len(p) <= 120) for p in f["aliases"]
        ):
            raise ValueError("Gold aliases must be nonempty regex expressions")
        for alias in f["aliases"]:
            re.compile(alias, flags=re.I | re.S)
        if not isinstance(f["required_stages"], list) or not f["required_stages"] or any(
            s not in STAGES for s in f["required_stages"]
        ):
            raise ValueError("Gold finding has invalid required stages")
    return gold


def replay(gold, report, source_sha: str, policy_sha: str, label: str):
    problems = []
    def flag(reason):
        if reason not in problems:
            problems.append(reason)

    if not isinstance(report, dict) or report.get("kind") != "clarity-independent-review":
        return {"label": label, "benchmark_pass": False,
                "recomputed_aggregate": "BLOCKED", "problems": ["INVALID_REVIEW_PACKET"]}
    if report.get("input_file_sha256") != source_sha:
        flag("REVIEW_SOURCE_MISMATCH")
    if report.get("policy_file_sha256") != policy_sha:
        flag("REVIEW_POLICY_MISMATCH")
    if report.get("pilot_with_draft_policy") is not False:
        flag("DRAFT_OR_UNKNOWN_POLICY_PILOT")

    lint = report.get("deterministic")
    run = report.get("run")
    if not isinstance(lint, dict) or not isinstance(run, dict):
        flag("MISSING_GATE_REPORT")
        return {"label": label, "benchmark_pass": False,
                "recomputed_aggregate": "BLOCKED", "problems": problems}
    if lint.get("kind") != "clarity-deterministic-quality-report":
        flag("INVALID_DETERMINISTIC_REPORT")
    if not isinstance(run.get("results"), dict) or set(run["results"]) != set(STAGES):
        flag("INCOMPLETE_REVIEW_STAGES")
        return {"label": label, "benchmark_pass": False,
                "recomputed_aggregate": "BLOCKED", "problems": problems}

    results = {}
    for stage in STAGES:
        try:
            results[stage] = check_stage(stage, run["results"][stage])
        except (ValueError, AttributeError, TypeError) as exc:
            flag("INVALID_STAGE_" + stage.upper())
    if len(results) != len(STAGES):
        return {"label": label, "benchmark_pass": False,
                "recomputed_aggregate": "BLOCKED", "problems": problems}
    # The run's own aggregate, approval flags, model name and provider receipt
    # have NO authority in a benchmark. Recompute using one invariant scorer.
    # backend='claude' means check semantic conditions independently of origin,
    # NOT that authenticated Claude ran or that an approval was issued.
    policy = {"adopted": True, "risk_register_status": "APPROVED"}
    agg = summarize(lint, results, policy, "claude")
    computed = agg["status"]
    prior = run.get("aggregate")
    if not isinstance(prior, dict) or prior.get("status") != computed or (
        prior.get("ready_for_handover") is not False or
        prior.get("publication_authority") is not False
    ):
        flag("UNTRUSTED_AGGREGATE_CLAIM")
    if problems:
        computed = "BLOCKED"
    if computed != gold["expected_aggregate"]:
        flag("WRONG_AGGREGATE")
    for f in gold["required_findings"]:
        for stage in f["required_stages"]:
            text = " ".join(
                " ".join(str(item.get(k,"")) for k in ("summary", "source", "proposed_action"))
                for item in results[stage]["findings"]
                if item.get("severity") in ("BLOCKER", "WARN")
            )
            if not any(re.search(p, text, flags=re.I | re.S) for p in f["aliases"]):
                flag("MISSED_" + f["id"] + "_" + stage.upper())
    return {"label": label, "benchmark_pass": not problems, "recomputed_aggregate": computed,
            "problems": problems}


def compare(gold, story_bytes: bytes, policy_bytes: bytes, reports: dict):
    story_sha, policy_sha = digest(story_bytes), digest(policy_bytes)
    validate_gold(gold, story_bytes.decode("utf-8"), story_sha, policy_sha)
    if not isinstance(reports, dict) or len(reports) < 2 or len(reports) > 8:
        raise ValueError("Compare 2–8 named independent review packets")
    results = [replay(gold, value, story_sha, policy_sha, label)
               for label, value in sorted(reports.items())]
    statuses = {x["recomputed_aggregate"] for x in results}
    return {
        "schema_version": 1, "kind": "clarity-comparative-quality-benchmark",
        "case_id": gold["case_id"], "source_sha256": story_sha,
        "policy_sha256": policy_sha,
        "benchmark_result": "PASS" if all(x["benchmark_pass"] for x in results)
                              and len(statuses) == 1 else "FAIL",
        "cross_model_agreement": len(statuses) == 1,
        "reviews": results,
        "ready_for_handover": False, "publication_authority": False,
        "note": "Compares supplied reports. Cannot prove model identity, actual inference, independent sessions or project approval."
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--story", type=Path, required=True)
    p.add_argument("--policy", type=Path, required=True)
    p.add_argument("--gold", type=Path, required=True)
    p.add_argument("--review", action="append", required=True,
                   help="Label=/private/review.json; at least two distinct labels")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        reports = {}
        for value in args.review:
            label, sep, path = value.partition("=")
            if not sep or not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", label) or label in reports:
                raise ValueError("Invalid or duplicate reviewer label")
            reports[label] = parse(Path(path))[0]
        output = compare(parse(args.gold)[0], args.story.read_bytes(),
                         args.policy.read_bytes(), reports)
        target = args.output.absolute()
        if target.exists() or any(x.is_symlink() for x in (target, *target.parents)):
            raise ValueError("Output exists or symlink path")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8") as fp:
            json.dump(output, fp, indent=2)
            fp.write("\n")
        print("Clarity cross-model benchmark: " + output["benchmark_result"] +
              " (NOT an approval)")
        return 0 if output["benchmark_result"] == "PASS" else 3
    except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
