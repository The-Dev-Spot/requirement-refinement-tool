"""Offline mocked tests for no-tool question research; never invoke a model."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from question_relevance_research import (
    build_prompt, research, run_claude_research, schema_for,
)
from test_question_relevance_gate import RelevanceGateTest


class ResearchProposerTests(unittest.TestCase):
    def setUp(self):
        self.case = RelevanceGateTest(methodName="test_unclassified_questions_are_preserved_not_sent_to_inbox")
        self.case.setUp()
        self.s, self.p, self.e, self.r = (
            self.case.s, self.case.p, self.case.e, self.case.r)
        self.prev, self.hashes = self.case.prev, self.case.hashes
        self.ids = [t["topic_id"] for t in self.prev["question_topics"]]

    def choose(self, needle):
        return self.case.topic(needle)

    def decision(self, topic, d, *, answer="", quote="", source="S-002", duplicate=None):
        return {
            "topic_id": topic, "disposition": d,
            "rationale": "Sufficiently detailed proposed research disposition.",
            "answer": answer,
            "evidence": [{"source_id": source, "quote": quote}] if quote else [],
            "duplicate_of": duplicate,
        }

    def test_research_prompt_bounded_and_all_topics_pinned(self):
        prompt, ids = build_prompt(self.prev, self.e, None, count=3)
        self.assertEqual(ids, self.ids)
        self.assertIn(self.prev["review_report_sha256"], prompt)
        self.assertIn("pinned_github_excerpts", prompt)
        self.assertIn("historical Linear item", prompt)
        self.assertIn("No code runs", prompt)
        self.assertIn("GitHub-only operational intake", prompt)
        self.assertNotIn("github_pat_", prompt)
        with self.assertRaisesRegex(ValueError, "Invalid question range"):
            build_prompt(self.prev, self.e, None, start=100)
        with self.assertRaisesRegex(ValueError, "Invalid question range"):
            build_prompt(self.prev, self.e, None, count=41)
        self.assertEqual(schema_for(3)["properties"]["decisions"]["minItems"], 3)

    def test_run_model_receipt_and_no_tool_contract(self):
        ids = self.ids[:1]
        data = {
            "structured_output": {"decisions": [
                self.decision(ids[0], "NEEDS_TECHNICAL_VERIFICATION")]},
            "model": "claude-opus-5-5",
            "modelUsage": {"claude-opus-5-5": {"inputTokens": 100}},
            "session_id": "independent-model-session-999",
            "total_cost_usd": 0.2,
        }
        fake = SimpleNamespace(returncode=0, stdout=json.dumps(data), stderr="")
        with patch("question_relevance_research.is_hosted_session", return_value=False), \
                patch("question_relevance_research.subprocess.run", return_value=fake) as run:
            decisions, receipt = run_claude_research(
                "Synthetic prompt", ids, model="claude-opus-5-5",
                max_budget=2, timeout=60)
        cmd = run.call_args.args[0]
        self.assertIn("--restricted", cmd)
        self.assertIn("--disallowedTools", cmd)
        self.assertIn("--no-session-persistence", cmd)
        self.assertIn("--max-turns", cmd)
        self.assertIn("--max-budget-usd", cmd)
        self.assertEqual(run.call_args.kwargs["input"], "Synthetic prompt")
        self.assertTrue(receipt["model_verified"])
        self.assertEqual(receipt["question_count"], 1)
        self.assertEqual(decisions[0]["topic_id"], ids[0])

    def test_model_must_reveal_true_identity_and_cover_selection(self):
        ids = self.ids[:1]
        data = {
            "structured_output": {"decisions": [
                self.decision(ids[0], "NEEDS_OWNER_DECISION")]},
            "model": "claude-sonnet-5-5",
            "session_id": "other-session",
        }
        fake = SimpleNamespace(returncode=0, stdout=json.dumps(data), stderr="")
        with patch("question_relevance_research.is_hosted_session", return_value=False), \
                patch("question_relevance_research.subprocess.run", return_value=fake):
            with self.assertRaisesRegex(ValueError, "identity/session"):
                run_claude_research("Test", ids, model="claude-opus-5-5",
                                    max_budget=2, timeout=60)
        data["model"] = "claude-opus-5-5"
        data["structured_output"]["decisions"][0]["topic_id"] = "topic-" + "f" * 20
        fake.stdout = json.dumps(data)
        with patch("question_relevance_research.is_hosted_session", return_value=False), \
                patch("question_relevance_research.subprocess.run", return_value=fake):
            with self.assertRaisesRegex(ValueError, "omitted or substituted"):
                run_claude_research("Test", ids, model="claude-opus-5-5",
                                    max_budget=2, timeout=60)

    def test_research_resolves_only_candidates_and_preserves_other_questions(self):
        one = self.choose("collector documented")
        owner = self.choose("approved")
        duplicate = self.choose("authorized")
        proposed = [
            self.decision(one, "ANSWERED_BY_GITHUB_EVIDENCE",
                          answer="The current file documents it.",
                          quote="GitHub-only operational intake."),
            self.decision(owner, "NEEDS_OWNER_DECISION"),
            self.decision(duplicate, "DUPLICATE_OF", duplicate=owner),
        ]
        receipt = {
            "session_id": "unique-research-session",
            "model_verified": True,
            "model_requested": "claude-opus-5-5",
            "model_resolved": "claude-opus-5-5",
            "provider": "claude-code",
        }
        with patch("question_relevance_research.run_claude_research",
                   return_value=(proposed, receipt)) as worker:
            result = research(
                self.s, self.p, self.e, self.r, self.prev, self.hashes,
                provider="claude", count=3)
        self.assertEqual(worker.call_count, 1)
        self.assertEqual(len(result["batch_topic_ids"]), 3)
        self.assertEqual(result["proposed_owner_question_ids"], [owner])
        self.assertFalse(result["inbox_import_authority"])
        self.assertFalse(result["automatic_question_suppression_authority"])
        self.assertFalse(result["approval_authority"])
        self.assertFalse(result["forge_dispatch_authority"])

    def test_invalid_quote_blocks_research_output(self):
        invalid = [self.decision(
            self.choose("collector documented"), "ANSWERED_BY_GITHUB_EVIDENCE",
            answer="Invented", quote="Made up quote to pass through.")]
        receipt = {"session_id": "fresh-session", "model_verified": True}
        with patch("question_relevance_research.run_claude_research",
                   return_value=(invalid, receipt)):
            with self.assertRaisesRegex(ValueError, "quote not present"):
                research(self.s, self.p, self.e, self.r, self.prev,
                         self.hashes, provider="claude", count=1)

    def test_invalid_baseline_never_spends_model_calls(self):
        tampered = json.loads(json.dumps(self.prev))
        tampered["review_report_sha256"] = "a" * 64
        with patch("question_relevance_research.run_claude_research") as worker:
            with self.assertRaisesRegex(ValueError, "preview differs"):
                research(self.s, self.p, self.e, self.r, tampered,
                         self.hashes, provider="claude")
        worker.assert_not_called()

    def test_historical_context_only_informs_not_approves(self):
        history = self.case.history()
        prompt, _ = build_prompt(self.prev, self.e, history)
        self.assertIn("Earlier discussion", prompt)
        history["current_policy_authority"] = True
        with patch("question_relevance_research.run_claude_research") as worker:
            with self.assertRaisesRegex(ValueError, "cannot assert current authority"):
                research(self.s, self.p, self.e, self.r, self.prev,
                         self.hashes, history=history, provider="claude")
        worker.assert_not_called()

    def test_reused_review_session_fails_closed(self):
        old_sessions = [v.get("session_id") for v in
                        self.r["run"]["receipts"].values()]
        old = next(x for x in old_sessions if x)
        proposed = [self.decision(x, "NEEDS_TECHNICAL_VERIFICATION")
                    for x in self.ids]
        with patch("question_relevance_research.run_claude_research",
                   return_value=(proposed, {"session_id": old, "model_verified": True})):
            with self.assertRaisesRegex(ValueError, "reused"):
                research(self.s, self.p, self.e, self.r, self.prev,
                         self.hashes, provider="claude", count=3)


if __name__ == "__main__":
    unittest.main()
