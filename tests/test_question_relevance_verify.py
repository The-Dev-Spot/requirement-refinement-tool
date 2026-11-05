"""No-network regressions for the separate evidence/challenge model session."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from evidence_context import canonical, digest
from question_relevance_gate import prepare_gate
from question_relevance_research import build_prompt, research
from question_relevance_verify import (
    build_challenge_prompt, challenge, run_model, validate_assessments,
    validate_research,
)
from test_question_relevance_gate import RelevanceGateTest


class IndependentQuestionChallengeTests(unittest.TestCase):
    def setUp(self):
        case = RelevanceGateTest(
            methodName="test_unclassified_questions_are_preserved_not_sent_to_inbox")
        case.setUp()
        self.case = case
        self.s, self.p, self.e = case.s, case.p, case.e
        self.report, self.prev, self.hashes = case.r, case.prev, case.hashes
        self.doc_id = case.topic("collector documented")
        self.approval_id = case.topic("approved")
        self.other_id = case.topic("authorized")
        self.doc_quote = "GitHub-only operational intake."
        self.primary = {
            "topic_id": self.doc_id,
            "disposition": "ANSWERED_BY_GITHUB_EVIDENCE",
            "rationale": "Pinned repository documentation directly describes the collector.",
            "answer": "Current documentation names the GitHub-only collector.",
            "evidence": [{"source_id": "S-002", "quote": self.doc_quote}],
            "duplicate_of": None,
        }
        self.owner = {
            "topic_id": self.approval_id,
            "disposition": "NEEDS_OWNER_DECISION",
            "rationale": "No approved rollout authority was identified by this proposal.",
            "answer": "", "evidence": [], "duplicate_of": None,
        }
        self.dupe = {
            "topic_id": self.other_id,
            "disposition": "DUPLICATE_OF",
            "rationale": "Both ask who authorized the same deployment action.",
            "answer": "", "evidence": [], "duplicate_of": self.approval_id,
        }
        prompt, selected = build_prompt(self.prev, self.e, None, count=3)
        assert len(selected) == 3
        receipt = {
            "provider": "claude-code", "model_verified": True,
            "model_requested": "claude-opus-5-5",
            "model_resolved": "claude-opus-5-5",
            "session_id": "fresh-independent-researcher",
            "question_count": 3,
            "prompt_sha256": digest(prompt.encode()),
        }
        with patch("question_relevance_research.run_claude_research",
                   return_value=([self.primary, self.owner, self.dupe], receipt)):
            self.research_result = research(
                self.s, self.p, self.e, self.report, self.prev, self.hashes,
                count=3, provider="claude")
        self.assessments = [
            {
                "topic_id": self.doc_id, "outcome": "CONCUR",
                "rationale": "The pinned documentation explicitly describes the relevant fact.",
                "source_quotes": [{"source_id": "S-002", "quote": self.doc_quote}],
                "missing_evidence": "",
            },
            {
                "topic_id": self.approval_id, "outcome": "INSUFFICIENT_EVIDENCE",
                "rationale": "Current authorized owner identity was not established by the excerpts.",
                "source_quotes": [],
                "missing_evidence": "Current approved decision register is required.",
            },
            {
                "topic_id": self.other_id, "outcome": "CONCUR",
                "rationale": "Both questions refer to the same rollout authorization decision.",
                "source_quotes": [],
                "missing_evidence": "",
            },
        ]
        self.receipt = {
            "provider": "claude-code", "model_verified": True,
            "model_requested": "claude-opus-5-5",
            "model_resolved": "claude-opus-5-5",
            "session_id": "different-independent-challenger",
            "question_count": 3, "prompt_sha256": "a" * 64,
        }

    def verify(self, research_result=None):
        return validate_research(
            self.s, self.p, self.e, self.report, self.prev, self.hashes,
            research_result or self.research_result)

    def test_replay_research_proposal_is_non_authoritative(self):
        result = self.verify()
        self.assertFalse(result["approval_authority"])
        self.assertEqual(result["proposed_owner_question_ids"], [self.approval_id])
        self.assertEqual(len(result["topics"]), 3)
        self.assertEqual(result["counts"]["DUPLICATE_OF"], 1)

    def test_forged_identity_source_and_batch_are_rejected(self):
        data = copy.deepcopy(self.research_result)
        data["receipt"]["prompt_sha256"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "exact prompt"):
            self.verify(data)
        data = copy.deepcopy(self.research_result)
        data["batch_topic_ids"].reverse()
        with self.assertRaisesRegex(ValueError, "original question order"):
            self.verify(data)
        data = copy.deepcopy(self.research_result)
        data["proposals"]["decisions"].pop()
        with self.assertRaisesRegex(ValueError, "omitted or injected"):
            self.verify(data)
        data = copy.deepcopy(self.research_result)
        fact = next(x for x in data["proposals"]["decisions"]
                    if x["topic_id"] == self.doc_id)
        fact["evidence"][0]["quote"] = "A fake assertion not in this GitHub file."
        with self.assertRaisesRegex(ValueError, "quote not present"):
            self.verify(data)

    def test_challenge_prompt_is_grounded_and_not_preapproved(self):
        self.verify()
        prompt = build_challenge_prompt(self.prev, self.e, self.research_result)
        self.assertIn("CHALLENGE_PACKET_JSON", prompt)
        self.assertIn(self.doc_quote, prompt)
        self.assertIn("semantic sufficiency", prompt)
        self.assertIn("source excerpts", prompt)
        self.assertIn(self.approval_id, prompt)
        self.assertIn(self.owner["rationale"], prompt)
        self.assertLess(len(prompt.encode()), 120001)

    def test_valid_challenge_preserves_no_authority(self):
        with patch("question_relevance_verify.run_model",
                   return_value=(self.assessments, self.receipt)):
            output = challenge(
                self.s, self.p, self.e, self.report, self.prev,
                self.hashes, self.research_result, provider="claude")
        self.assertTrue(output["independent_model_challenge_completed"])
        self.assertEqual(output["counts"]["CONCUR"], 2)
        self.assertEqual(output["counts"]["INSUFFICIENT_EVIDENCE"], 1)
        self.assertEqual(output["target_issue"], self.prev["target_issue"])
        for key in ("current_source_truth_verified",
                    "semantic_answer_authority_verified",
                    "owner_decision_authority_verified",
                    "automatic_question_suppression_authority",
                    "inbox_import_authority", "approval_authority",
                    "forge_dispatch_authority"):
            self.assertFalse(output[key])

    def test_independent_citation_cannot_be_invented_or_issue_only(self):
        wrong = copy.deepcopy(self.assessments)
        wrong[0]["source_quotes"][0]["quote"] = "A nonexistent GitHub citation!"
        with self.assertRaisesRegex(ValueError, "pinned source"):
            validate_assessments(wrong, self.research_result, self.e, None)
        wrong = copy.deepcopy(self.assessments)
        wrong[0]["source_quotes"] = [{
            "source_id": "S-001",
            "quote": "GitHub Issues are the source of truth",
        }]
        with self.assertRaisesRegex(ValueError, "independent GitHub citation"):
            validate_assessments(wrong, self.research_result, self.e, None)

    def test_omitted_question_or_duplicate_quote_refused(self):
        with self.assertRaisesRegex(ValueError, "count mismatch"):
            validate_assessments(self.assessments[:2],
                                 self.research_result, self.e, None)
        wrong = copy.deepcopy(self.assessments)
        wrong[1]["topic_id"] = wrong[0]["topic_id"]
        with self.assertRaisesRegex(ValueError, "Malformed independent"):
            validate_assessments(wrong, self.research_result, self.e, None)

    def test_reused_researcher_or_review_session_fails(self):
        for session in (
            self.research_result["receipt"]["session_id"],
            self.report["run"]["receipts"]["investigator"]["session_id"],
        ):
            receipt = dict(self.receipt, session_id=session)
            with patch("question_relevance_verify.run_model",
                       return_value=(self.assessments, receipt)):
                with self.subTest(session=session), self.assertRaisesRegex(
                        ValueError, "reused"):
                    challenge(self.s, self.p, self.e, self.report, self.prev,
                              self.hashes, self.research_result, provider="claude")

    def test_baseline_fails_before_paid_model(self):
        data = copy.deepcopy(self.research_result)
        data["target_issue"] = "example/repository#4"
        with patch("question_relevance_verify.run_model") as caller:
            with self.assertRaisesRegex(ValueError, "authority mismatch"):
                challenge(self.s, self.p, self.e, self.report, self.prev,
                          self.hashes, data, provider="claude")
        caller.assert_not_called()

    def test_model_cli_restricted_and_identity_checked(self):
        data = {
            "structured_output": {"assessments": self.assessments},
            "model": "claude-opus-5-5",
            "modelUsage": {"claude-opus-5-5": {"inputTokens": 100}},
            "session_id": "challenge-session-123",
            "total_cost_usd": 0.25,
        }
        fake = SimpleNamespace(returncode=0, stdout=json.dumps(data), stderr="")
        with patch("question_relevance_verify.is_hosted_session", return_value=False), \
                patch("question_relevance_verify.subprocess.run", return_value=fake) as run:
            observations, receipt = run_model(
                "Synthetic challenge", self.research_result["batch_topic_ids"],
                model="claude-opus-5-5", max_budget=2, timeout=60)
        cmd = run.call_args.args[0]
        for flag in ("--restricted", "--disallowedTools", "--no-session-persistence",
                     "--max-turns", "--max-budget-usd"):
            self.assertIn(flag, cmd)
        self.assertTrue(receipt["model_verified"])
        self.assertEqual(len(observations), 3)
        self.assertEqual(run.call_args.kwargs["input"], "Synthetic challenge")
        data["model"] = "claude-sonnet-5-5"
        fake.stdout = json.dumps(data)
        with patch("question_relevance_verify.is_hosted_session", return_value=False), \
                patch("question_relevance_verify.subprocess.run", return_value=fake):
            with self.assertRaisesRegex(ValueError, "identity invalid"):
                run_model("Test", self.research_result["batch_topic_ids"],
                          model="claude-opus-5-5", max_budget=2, timeout=60)


if __name__ == "__main__":
    unittest.main()
