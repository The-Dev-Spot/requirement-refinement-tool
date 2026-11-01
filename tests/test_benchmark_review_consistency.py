"""Synthetic provider-neutral Clarity QA benchmark, no live AI provider.

Uses Clarity's existing review-report format. Reviewer A and B are fabricated
fixture variants, NOT ChatGPT or Claude model calls. Expected conflicts come
from an artificial analogue of HOM-1972 with no private Linear material.
"""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_review_consistency import compare, digest
from accept_requirements import canonical
from test_acceptance_proposal import base


def positive_case():
    data=base()
    story=json.loads(data["story_data"])
    case={
        "schema_version":1,"case_id":"FORGE-DEMO-SYNTHETIC",
        "source_sha256":digest(data["story_data"]),
        "policy_sha256":digest(data["review_policy_data"]),
        "expected_aggregate":"REVIEWABLE_CANDIDATE",
        "required_findings":[],
        "source_anchors":[story["title"],story["payload"]]
    }
    a=json.loads(data["review_data"])
    b=copy.deepcopy(a)
    b["run"]["results"]["challenger"]["summary"]="Another explanation of the same clean synthetic requirements"
    b["run"]["results"]["evaluator"]["dimensions"][0]["rationale"]="Alternative wording; same PASS evidence and decision"
    return case,data["story_data"],data["review_policy_data"],a,b


def contradiction_case():
    data=base()
    story=json.loads(data["story_data"])
    story["title"]="Fictional two-pool pilot"
    story["payload"]=(
        "New approved topology: four worker slots, Clarity and Forge each with normal and "
        "reserved-critical lanes. Historical draft: at most two total worker containers. "
        "New admission: no per-issue Start for accepted defects. Historical supervised "
        "pilot says a human-start authorization is required for every job."
    )
    s=json.dumps(story,separators=(",",":")).encode()
    review=json.loads(data["review_data"])
    review["input_file_sha256"]=digest(s)
    for item in review["run"]["receipts"].values():
        item["input_sha256"]=digest(canonical(story))
    for stage in ("investigator","challenger"):
        review["run"]["results"][stage]["verdict"]="WARN"
        review["run"]["results"][stage]["findings"]=[
            {"id":"F-cap","severity":"BLOCKER",
             "summary":"Conflicting worker capacity: four pool slots versus two total workers",
             "source":"Fictional top-level decision vs historical draft",
             "proposed_action":"Choose authoritative worker capacity"},
            {"id":"F-start","severity":"BLOCKER",
             "summary":"Per-job human-start authorization contradicts no per-issue Start policy",
             "source":"Fictional latest and historical sections",
             "proposed_action":"Scope human-start to supervised experiment"}
        ]
    review["run"]["results"]["evaluator"]["verdict"]="WARN"
    review["run"]["results"]["evaluator"]["dimensions"][7]["status"]="FAIL"
    review["run"]["aggregate"]["status"]="BLOCKED"
    b=copy.deepcopy(review)
    for stage in ("investigator","challenger"):
        b["run"]["results"][stage]["findings"][0]["summary"]="Different max worker slot cap: 4 versus 2"
        b["run"]["results"][stage]["findings"][1]["summary"]="Manual per-task start conflicts with automatic issue admission"
    case={
        "schema_version":1,"case_id":"M0-CAPACITY-SYNTHETIC",
        "source_sha256":digest(s),
        "policy_sha256":digest(data["review_policy_data"]),
        "expected_aggregate":"BLOCKED",
        "source_anchors":["four worker slots, Clarity and Forge",
                          "at most two total worker containers",
                          "no per-issue Start", "human-start authorization"],
        "required_findings":[
            {"id":"CAPACITY_CONFLICT","aliases":["worker (?:capacity|slot|pool)",
                                                  "(?:four|4).{0,75}(?:two|2)"],
             "required_stages":["investigator","challenger"]},
            {"id":"AUTHORIZATION_CONFLICT","aliases":["human[- ]start",
                                                       "per[- ]task start",
                                                       "per[- ]job.*(?:start|authorization)"],
             "required_stages":["investigator","challenger"]}
        ]
    }
    return case,s,data["review_policy_data"],review,b


class ModelNeutralBenchmarks(unittest.TestCase):
    def test_two_independent_wordings_clean_outcome_agree(self):
        c,s,p,a,b=positive_case()
        result=compare(c,s,p,{"reviewer_a":a,"reviewer_b":b})
        self.assertEqual(result["benchmark_result"],"PASS")
        self.assertEqual(result["reviews"][0]["recomputed_aggregate"],"REVIEWABLE_CANDIDATE")
        self.assertFalse(result["ready_for_handover"])
        self.assertFalse(result["publication_authority"])

    def test_two_differently_worded_blockers_detect_same_golden_conflicts(self):
        c,s,p,a,b=contradiction_case()
        result=compare(c,s,p,{"reviewer_a":a,"reviewer_b":b})
        self.assertEqual(result["benchmark_result"],"PASS",result)
        self.assertEqual(result["reviews"][0]["recomputed_aggregate"],"BLOCKED")

    def test_one_reviewer_misses_conflict_is_explicit_failure(self):
        c,s,p,a,b=contradiction_case()
        b["run"]["results"]["challenger"]["findings"].pop(1)
        result=compare(c,s,p,{"reviewer_a":a,"reviewer_b":b})
        self.assertEqual(result["benchmark_result"],"FAIL")
        self.assertTrue(any("MISSED_AUTHORIZATION_CONFLICT_CHALLENGER" in x["problems"]
                            for x in result["reviews"]))

    def test_model_claims_clean_but_gold_expects_block(self):
        c,s,p,a,b=contradiction_case()
        b["run"]["aggregate"]["status"]="REVIEWABLE_CANDIDATE"
        for stage in ("investigator","challenger"):
            b["run"]["results"][stage].update(verdict="PASS",findings=[])
        b["run"]["results"]["evaluator"]["verdict"]="PASS"
        for d in b["run"]["results"]["evaluator"]["dimensions"]:
            d["status"]="PASS"
        result=compare(c,s,p,{"reviewer_a":a,"reviewer_b":b})
        self.assertEqual(result["benchmark_result"],"FAIL")
        self.assertIn("WRONG_AGGREGATE",result["reviews"][1]["problems"])

    def test_reviewer_must_be_bound_to_exact_input_and_policy(self):
        c,s,p,a,b=positive_case()
        b["policy_file_sha256"]="1"*64
        result=compare(c,s,p,{"reviewer_a":a,"reviewer_b":b})
        self.assertEqual(result["benchmark_result"],"FAIL")
        self.assertIn("REVIEW_POLICY_MISMATCH",result["reviews"][1]["problems"])

    def test_wrong_or_stale_gold_source_rejected(self):
        c,s,p,a,b=positive_case()
        with self.assertRaisesRegex(ValueError,"not bound to exact"):
            compare(c,s+b" ",p,{"reviewer_a":a,"reviewer_b":b})
        c["source_anchors"]=["A totally missing sentence from the record."]
        with self.assertRaisesRegex(ValueError,"source anchor missing"):
            compare(c,s,p,{"reviewer_a":a,"reviewer_b":b})

    def test_linter_warn_fails_clean_gold_even_with_model_pass(self):
        c,s,p,a,b=positive_case()
        a["deterministic"]["status"]="WARN"
        r=compare(c,s,p,{"reviewer_a":a,"reviewer_b":b})
        self.assertEqual(r["benchmark_result"],"FAIL")
        self.assertIn("WRONG_AGGREGATE",r["reviews"][0]["problems"])

    def test_incomplete_d1_to_d10_is_not_silently_ignored(self):
        c,s,p,a,b=positive_case()
        a["run"]["results"]["evaluator"]["dimensions"].pop()
        r=compare(c,s,p,{"reviewer_a":a,"reviewer_b":b})
        self.assertEqual(r["benchmark_result"],"FAIL")
        self.assertIn("INVALID_STAGE_EVALUATOR",r["reviews"][0]["problems"])

    def test_missing_challenger_fails(self):
        c,s,p,a,b=positive_case()
        b["run"]["results"].pop("challenger")
        r=compare(c,s,p,{"reviewer_a":a,"reviewer_b":b})
        self.assertEqual(r["benchmark_result"],"FAIL")
        self.assertIn("INCOMPLETE_REVIEW_STAGES",r["reviews"][1]["problems"])

    def test_claimed_ready_cannot_change_benchmark_result(self):
        c,s,p,a,b=positive_case()
        b["run"]["aggregate"]["status"]="READY"
        b["run"]["aggregate"]["ready_for_handover"]=True
        result=compare(c,s,p,{"reviewer_a":a,"reviewer_b":b})
        self.assertEqual(result["benchmark_result"],"PASS")
        self.assertFalse(result["publication_authority"])
        self.assertFalse(result["ready_for_handover"])


if __name__=="__main__":
    unittest.main()
