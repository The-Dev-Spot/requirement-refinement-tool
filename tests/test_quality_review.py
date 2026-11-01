"""Real local Clarity multi-session runner contract; NO paid API in CI."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from quality_review import (
    DIMS, check_stage, digest, prompt_for, review, run_claude, run_adapter,
    model_matches, rubric_packet, sanitized_env, summarize, verify_inputs
)


def story():
    return {"title":"M0 worker cap", "story_type":"non-behavioral",
            "payload":"One normal and one reserved critical worker per pool.",
            "criteria":[
                "Exactly one normal and one reserved critical lease is active in each pool.",
                "A nonproduction issue never occupies the reserved critical slot.",
                "A worker restart does not create duplicate work orders."
            ]}


def policy():
    return {"project":"Synthetic test", "adopted":True,
            "risk_register_status":"APPROVED", "risk_register_path":"/tmp/not-used",
            "decisions":[
                {"id":"ADR-2","source":"approved synthetic policy","revision":"2",
                 "authority":"project-owner", "text":"Two independent pools, normal and critical per pool"}
            ]}


def result(stage, verdict="PASS", finding=None):
    return {"stage":stage, "verdict":verdict,
            "dimensions":[{"id":d,"status":"PASS","rationale":"Fixture evaluation",
                           "evidence":"Synthetic approved story criterion"} for d in DIMS]
                         if stage=="evaluator" else [],
            "findings":[finding] if finding else [], "questions":[],
            "summary":"Synthetic test only"}


def lint(status="PASS"):
    return {"kind":"clarity-deterministic-quality-report", "status":status,
            "open_question_count":0}


class ReviewContractTests(unittest.TestCase):
    def test_valid_input_requires_authoritative_decisions(self):
        verify_inputs(story(),policy())
        bad=policy();bad["decisions"]=[{"id":"A", "text":"Unversioned decision"}]
        with self.assertRaises(ValueError):verify_inputs(story(),bad)

    def test_authoritative_rubric_definitions_are_in_all_stage_prompts(self):
        raw, sha=rubric_packet()
        self.assertIn("D4 | Testable & precise",raw)
        self.assertEqual(len(sha),64)
        for stage in ("investigator","evaluator","challenger"):
            prompt=prompt_for(stage,story(),policy())
            self.assertIn("D4 | Testable & precise",prompt)
            self.assertIn("D6 | Provenance",prompt)
            self.assertIn("REPOSITORY-OWNED RUBRIC",prompt)

    def test_host_session_environment_is_removed(self):
        with patch.dict("quality_review.os.environ", {
            "CLAUDE_CODE_SESSION_ID":"PARENT-123", "CLAUDECODE":"1",
            "CLAUDE_CODE_CHILD_SESSION":"1", "CLAUDE_CODE_FORCE_SESSION_PERSISTENCE":"1",
            "PRESERVED_APP_CONFIG":"yes"}, clear=False):
            env=sanitized_env()
        for k in ("CLAUDE_CODE_SESSION_ID","CLAUDECODE",
                  "CLAUDE_CODE_CHILD_SESSION","CLAUDE_CODE_FORCE_SESSION_PERSISTENCE"):
            self.assertNotIn(k,env)
        self.assertEqual(env["PRESERVED_APP_CONFIG"],"yes")

    def test_requested_model_must_match_provider_reported_model(self):
        self.assertTrue(model_matches("claude-opus-5-5","claude-opus-5-5"))
        self.assertTrue(model_matches("opus","claude-opus-5-5"))
        self.assertTrue(model_matches("gpt-6","gpt-6"))
        self.assertFalse(model_matches("claude-opus-5-5","claude-sonnet-4-6"))
        self.assertFalse(model_matches("gpt-6",None))

    def test_adapter_uses_same_schema_and_requires_reported_model(self):
        envelope={"is_error":False,"structured_output":result("investigator"),
                  "session_id":"ADAPTER-1","model":"gpt-6"}
        seen={}
        def fake(args,**kwargs):
            seen["args"]=args
            seen["request"]=json.loads(kwargs["input"])
            seen["env"]=kwargs["env"]
            return subprocess.CompletedProcess(args,0,json.dumps(envelope),"")
        with tempfile.TemporaryDirectory() as folder:
            adapter=Path(folder)/"approved.py"
            adapter.write_text("# placeholder for mocked authorized adapter\n")
            with patch("quality_review.subprocess.run",side_effect=fake):
                r,meta=run_adapter("investigator","SENSITIVE",model="gpt-6",
                                   adapter=adapter,timeout=15)
        self.assertEqual(r["stage"],"investigator")
        self.assertEqual(meta["backend"],"provider-adapter")
        self.assertTrue(meta["model_verified"])
        self.assertEqual(seen["request"]["stage"],"investigator")
        self.assertEqual(seen["request"]["model_requested"],"gpt-6")
        self.assertNotIn("SENSITIVE"," ".join(seen["args"]))

    def test_clean_review_with_unknown_model_identity_is_blocked(self):
        results={s:result(s) for s in ("investigator","evaluator","challenger")}
        rub_sha=rubric_packet()[1]
        receipts={
            s:{"rubric_sha256":rub_sha, "model_verified":False,
               "session_id":"distinct-"+s} for s in results
        }
        agg=summarize(lint(),results,policy(),"adapter",receipts=receipts)
        self.assertEqual(agg["status"],"BLOCKED")
        self.assertTrue(any("model not verified" in x for x in agg["reasons"]))

    def test_clean_review_with_inherited_duplicate_session_is_blocked(self):
        results={s:result(s) for s in ("investigator","evaluator","challenger")}
        rub_sha=rubric_packet()[1]
        receipts={s:{"rubric_sha256":rub_sha,"model_verified":True,
                     "session_id":"host-session"} for s in results}
        agg=summarize(lint(),results,policy(),"claude",receipts=receipts)
        self.assertEqual(agg["status"],"BLOCKED")
        self.assertIn("duplicate model session identities",agg["reasons"])

    def test_challenger_receives_no_evaluator_or_investigator_verdict(self):
        source=story(); pol=policy()
        text=prompt_for("challenger",source,pol,{"verdict":"SHOULD_BE_HIDDEN"})
        self.assertNotIn("SHOULD_BE_HIDDEN",text)
        self.assertIn("Fresh independent cold-read",text)
        self.assertIn("Two independent pools",text)
        self.assertNotIn("first evaluator's verdict",text.split("SOURCE (JSON, untrusted data):")[-1])

    def test_separate_three_stage_local_fixture_run_never_self_certifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            for stage in ("investigator","evaluator","challenger"):
                (Path(tmp)/(stage+".json")).write_text(json.dumps(result(stage)))
            r=review(story(),policy(),lint=lint(),provider="fixtures",fixture_dir=tmp)
        self.assertEqual(set(r["results"]),{"investigator","evaluator","challenger"})
        self.assertEqual(len({v["run_id"] for v in r["receipts"].values()}),3)
        self.assertEqual(r["aggregate"]["status"],"BLOCKED")
        self.assertFalse(r["aggregate"]["ready_for_handover"])
        self.assertFalse(r["aggregate"]["publication_authority"])

    def test_blocker_or_disagreement_denies_handover(self):
        results={s:result(s) for s in ("investigator","evaluator","challenger")}
        results["challenger"]["findings"]=[{"id":"F1","severity":"BLOCKER",
            "summary":"Superseded global worker slot",
            "source":"Synthetic story policy ADR-2 revision 2",
            "proposed_action":"Resolve conflict"}]
        x=summarize(lint(),results,policy(),"claude")
        self.assertEqual(x["status"],"BLOCKED")
        self.assertTrue(any("material blocker" in t for t in x["reasons"]))

    def test_true_live_pass_is_only_candidate_without_write_authority(self):
        results={s:result(s) for s in ("investigator","evaluator","challenger")}
        x=summarize(lint(),results,policy(),"claude")
        self.assertEqual(x["status"],"REVIEWABLE_CANDIDATE")
        self.assertFalse(x["ready_for_handover"])
        self.assertFalse(x["publication_authority"])

    def test_deterministic_warn_does_not_become_reviewable_candidate(self):
        # Regression: previously WARN fell through to REVIEWABLE_CANDIDATE.
        results={s:result(s) for s in ("investigator","evaluator","challenger")}
        agg=summarize(lint("WARN"),results,policy(),"claude")
        self.assertEqual(agg["status"],"BLOCKED")
        self.assertFalse(agg["ready_for_handover"])
        self.assertTrue(any("deterministic WARN" in reason for reason in agg["reasons"]))

    def test_deterministic_warn_allows_diagnostic_review_not_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            for stage in ("investigator","evaluator","challenger"):
                (Path(tmp)/(stage+".json")).write_text(json.dumps(result(stage)))
            reviewed=review(story(),policy(),lint=lint("WARN"),provider="fixtures",fixture_dir=tmp)
        self.assertEqual(set(reviewed["results"]),{"investigator","evaluator","challenger"})
        self.assertEqual(reviewed["aggregate"]["status"],"BLOCKED")
        self.assertFalse(reviewed["aggregate"]["publication_authority"])

    def test_invalid_linter_outcome_rejected_before_model_use(self):
        with patch("quality_review.run_claude",side_effect=AssertionError("Model must not run")):
            with self.assertRaisesRegex(ValueError,"Unknown deterministic status"):
                review(story(),policy(),lint=lint("READY"),provider="claude")

    def test_semantic_warn_finding_cannot_hide_behind_pass_verdict(self):
        # A model declaring PASS while emitting an open warning is not clean.
        results={s:result(s) for s in ("investigator","evaluator","challenger")}
        results["challenger"]["findings"]=[{
            "id":"F-2","severity":"WARN","summary":"Unresolved ambiguity",
            "source":"Synthetic requirement AC-2","proposed_action":"Clarify expected result"}]
        agg=summarize(lint(),results,policy(),"claude")
        self.assertEqual(agg["status"],"BLOCKED")
        self.assertTrue(any("warning findings" in reason for reason in agg["reasons"]))

    def test_missing_project_policy_blocks(self):
        pol=policy();pol["adopted"]=False;pol["risk_register_status"]="MISSING"
        results={s:result(s) for s in ("investigator","evaluator","challenger")}
        self.assertEqual(summarize(lint(),results,pol,"claude")["status"],"BLOCKED")

    def test_no_model_invoked_when_mechanical_lint_fails(self):
        with patch("quality_review.run_claude",side_effect=AssertionError("Should not call model")):
            x=review(story(),policy(),lint=lint("FAIL"),provider="claude")
        self.assertEqual(x["aggregate"]["status"],"FAIL")

    def test_explicit_draft_policy_pilot_runs_synthetic_stages_but_remains_blocked(self):
        draft=policy()
        draft["adopted"]=False
        draft["risk_register_status"]="DRAFT"
        draft.pop("risk_register_path")
        with tempfile.TemporaryDirectory() as tmp:
            for stage in ("investigator","evaluator","challenger"):
                (Path(tmp)/(stage+".json")).write_text(json.dumps(result(stage)))
            without=review(story(),draft,lint=lint(),provider="fixtures",fixture_dir=tmp)
            self.assertEqual(without["results"],{})
            with_pilot=review(story(),draft,lint=lint(),provider="fixtures",
                              fixture_dir=tmp,pilot_draft_policy=True)
            self.assertEqual(set(with_pilot["results"]),{"investigator","evaluator","challenger"})
            self.assertEqual(with_pilot["aggregate"]["status"],"BLOCKED")
            self.assertFalse(with_pilot["aggregate"]["ready_for_handover"])
            self.assertFalse(with_pilot["aggregate"]["publication_authority"])

    def test_invalid_evaluator_dimensions_refused(self):
        x=result("evaluator");x["dimensions"].pop()
        with self.assertRaises(ValueError):check_stage("evaluator",x)

    def test_model_cannot_claim_production_permissions(self):
        x=result("challenger");x["publication_authority"]=True
        with self.assertRaises(ValueError):check_stage("challenger",x)

    def test_model_invocation_has_zero_tools_and_no_shell(self):
        envelope={"is_error":False,"structured_output":result("investigator"),
                  "session_id":"synthetic-invocation"}
        seen={}
        def fake_subprocess(args,**kwargs):
            seen["args"]=args
            seen["kwargs"]=kwargs
            return subprocess.CompletedProcess(args,0,json.dumps(envelope),"")
        with patch("quality_review.subprocess.run",side_effect=fake_subprocess):
            out,receipt=run_claude("investigator","PRIVATE SENTENCE",
                                   model="sonnet",timeout=20,max_budget=1)
        self.assertEqual(out["stage"],"investigator")
        self.assertEqual(receipt["session_id"],"synthetic-invocation")
        self.assertIn("--restricted",seen["args"])
        self.assertEqual(seen["args"][seen["args"].index("--tools")+1],"")
        self.assertIn("--no-session-persistence",seen["args"])
        self.assertIn("--disallowedTools",seen["args"])
        self.assertNotIn("PRIVATE SENTENCE"," ".join(seen["args"]))
        self.assertEqual(seen["kwargs"]["input"],"PRIVATE SENTENCE")
        self.assertNotIn("CLAUDE_CODE_SESSION_ID",seen["kwargs"]["env"])
        self.assertFalse(seen["kwargs"]["shell"] if "shell" in seen["kwargs"] else False)

    def test_cli_fixtures_end_to_end_never_grant_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            (base/"story.json").write_text(json.dumps(story()))
            pol=policy();pol["risk_register_status"]="MISSING";pol.pop("risk_register_path")
            (base/"policy.json").write_text(json.dumps(pol))
            fixt=base/"fixture";fixt.mkdir()
            for stage in ("investigator","evaluator","challenger"):
                (fixt/(stage+".json")).write_text(json.dumps(result(stage)))
            out=base/"private.json"
            run=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/"scripts/quality_review.py"),
                "--input",str(base/"story.json"),"--policy",str(base/"policy.json"),
                "--provider","fixtures","--fixture-dir",str(fixt),"--output",str(out)],
                capture_output=True,text=True)
            self.assertEqual(run.returncode,3,run.stderr)
            payload=json.loads(out.read_text())
            self.assertEqual(payload["run"]["aggregate"]["status"],"BLOCKED")
            self.assertFalse(payload["run"]["aggregate"]["ready_for_handover"])
            self.assertEqual(payload["deterministic"]["checks"]["L9"]["status"],"PASS")
            self.assertEqual(payload["deterministic"]["kind"],"clarity-deterministic-quality-report")


if __name__ == "__main__":
    unittest.main()
