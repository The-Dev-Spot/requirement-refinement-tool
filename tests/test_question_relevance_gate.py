"""Offline fail-closed tests for the generic question relevance candidate gate."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from collect_github_context import collect
from preview_github_review import prepare
from question_relevance_gate import (prepare_gate, replay_preview,
                                     validate_history, validate_proposals)
from test_github_context import FakeGitHub, plan, story
from test_github_question_triage import eligible_policy, bound_data
from evidence_context import canonical, digest
from quality_review import write_private_report


class RelevanceGateTest(unittest.TestCase):
    def setUp(self):
        self.s = story()
        self.p = eligible_policy()
        self.e = collect(plan(), self.s, self.p, FakeGitHub())
        self.r, self.hashes = bound_data(self.s, self.p, self.e)
        self.r["run"]["results"]["investigator"]["questions"] = [
            "Where is the GitHub collector documented?",
            "Who approved this deploy?",
        ]
        self.r["run"]["results"]["evaluator"]["questions"] = [
            "Who authorized rollout?",
        ]
        self.r["run"]["results"]["challenger"]["questions"] = []
        self.prev = prepare(
            self.s, self.p, self.e, report=self.r,
            story_file_sha=self.hashes[0],
            policy_file_sha=self.hashes[1],
            evidence_file_sha=self.hashes[2],
        )
        self.assertEqual(self.prev["review_gate_status"], "BLOCKED")
        self.assertEqual(self.prev["topic_count"], 3)

    def topic(self, contains):
        return next(x["topic_id"] for x in self.prev["question_topics"]
                    if contains in x["question"])

    def proposal(self, decisions):
        return {"schema_version": 1,
                "kind": "clarity-question-disposition-proposals",
                "target_issue": self.prev["target_issue"],
                "review_report_sha256": self.prev["review_report_sha256"],
                "decisions": decisions}

    def entry(self, topic_id, d, *, quote="", answer="", duplicate=None,
              source="S-002"):
        return {
            "topic_id": topic_id, "disposition": d,
            "rationale": "Examined source and proposed this disposition.",
            "answer": answer,
            "evidence": ([{"source_id": source, "quote": quote}] if quote else []),
            "duplicate_of": duplicate,
        }

    def gate(self, **kwargs):
        return prepare_gate(self.s, self.p, self.e, self.r, self.prev,
                            self.hashes, **kwargs)

    def test_unclassified_questions_are_preserved_not_sent_to_inbox(self):
        result = self.gate()
        self.assertEqual(result["counts"]["NOT_YET_RESEARCHED"], 3)
        self.assertEqual(len(result["outstanding_research_ids"]), 3)
        self.assertEqual(result["proposed_owner_question_ids"], [])
        self.assertEqual(len(result["topics"]), 3)
        self.assertFalse(result["inbox_import_authority"])
        self.assertFalse(result["automatic_question_suppression_authority"])
        self.assertFalse(result["approval_authority"])
        self.assertFalse(result["forge_dispatch_authority"])
        for entry in result["topics"]:
            self.assertTrue(entry["original_question_ids"])
            self.assertFalse(entry["resolution_verified"])

    def test_current_github_code_quote_supports_only_candidate_answer(self):
        item = self.entry(
            self.topic("collector documented"), "ANSWERED_BY_GITHUB_EVIDENCE",
            answer="The collector is documented in a GitHub source file.",
            quote="GitHub-only operational intake.")
        result = self.gate(proposals=self.proposal([item]))
        self.assertEqual(result["counts"]["ANSWERED_BY_GITHUB_EVIDENCE"], 1)
        self.assertEqual(result["counts"]["NOT_YET_RESEARCHED"], 2)
        self.assertEqual(result["proposed_owner_question_ids"], [])
        self.assertTrue(result["requires_independent_evidence_verification"])
        self.assertFalse(result["topics"][0]["acceptance_authority"])

    def test_historical_linear_cannot_self_ratify_approval(self):
        item = self.entry(
            self.topic("approved"), "ANSWERED_BY_GITHUB_EVIDENCE",
            answer="Previously accepted", quote="GitHub Issues are the source of truth",
            source="S-001")
        with self.assertRaisesRegex(ValueError, "current GitHub"):
            self.gate(proposals=self.proposal([item]))

    def test_requires_real_quote_from_pinned_excerpt(self):
        item = self.entry(self.topic("collector documented"),
                          "ANSWERED_BY_GITHUB_EVIDENCE",
                          quote="This phrase is not in source!", answer="Resolved")
        with self.assertRaisesRegex(ValueError, "quote not present"):
            self.gate(proposals=self.proposal([item]))
        item["evidence"][0]["source_id"] = "S-999"
        with self.assertRaisesRegex(ValueError, "quote not present"):
            self.gate(proposals=self.proposal([item]))

    def test_owner_decisions_and_semantic_duplicates_are_proposals_only(self):
        primary = self.topic("approved")
        duplicate = self.topic("authorized")
        proposals = self.proposal([
            self.entry(primary, "NEEDS_OWNER_DECISION"),
            self.entry(duplicate, "DUPLICATE_OF", duplicate=primary),
        ])
        result = self.gate(proposals=proposals)
        self.assertEqual(result["proposed_owner_question_ids"], [primary])
        self.assertEqual(result["counts"]["DUPLICATE_OF"], 1)
        self.assertEqual(result["counts"]["NOT_YET_RESEARCHED"], 1)
        self.assertFalse(result["inbox_import_authority"])

    def test_disallow_duplicate_cycles_and_unspecified_primary(self):
        a, b = self.topic("approved"), self.topic("authorized")
        proposals = self.proposal([
            self.entry(a, "DUPLICATE_OF", duplicate=b),
            self.entry(b, "DUPLICATE_OF", duplicate=a),
        ])
        with self.assertRaisesRegex(ValueError, "primary"):
            self.gate(proposals=proposals)
        proposals["decisions"].pop()
        with self.assertRaisesRegex(ValueError, "primary"):
            self.gate(proposals=proposals)

    def test_forged_preview_and_forged_evidence_fail(self):
        tampered = copy.deepcopy(self.prev)
        tampered["question_topics"][0]["question"] = "Synthetic rewrite"
        with self.assertRaisesRegex(ValueError, "preview differs"):
            prepare_gate(self.s, self.p, self.e, self.r, tampered, self.hashes)
        tampered_e = copy.deepcopy(self.e)
        tampered_e["sources"][1]["excerpt"] = "New unpinned instructions."
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            prepare_gate(self.s, self.p, tampered_e, self.r, self.prev, self.hashes)

    def test_review_digest_and_target_are_locked(self):
        bad = self.proposal([])
        bad["target_issue"] = "sample-org/different#2"
        with self.assertRaisesRegex(ValueError, "exact GitHub review"):
            self.gate(proposals=bad)
        bad = self.proposal([])
        bad["review_report_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "exact GitHub review"):
            self.gate(proposals=bad)

    def history(self):
        excerpt = "Earlier discussion: notify only and require owner approval."
        return {
            "schema_version": 1, "kind": "clarity-linear-history-context",
            "target_issue": self.s["source_issue_id"],
            "review_scope": self.s["review_scope"],
            "story_sha256": digest(canonical(self.s).encode()),
            "policy_sha256": digest(canonical(self.p).encode()),
            "selection_sha256": "a" * 64,
            "status": "SOURCE_UNVERIFIED",
            "historical_sources": [{
                "id": "L-001", "provider": "linear",
                "source_kind": "HISTORICAL_ISSUE", "source_issue_id": "HIST-101",
                "url": "https://linear.app/example-workspace/issue/HIST-101",
                "revision": "2026-10-01T10:00:00Z",
                "scope": self.s["review_scope"],
                "project_mapping": "OPERATOR_SELECTED_UNVERIFIED",
                "authority": "HISTORICAL_UNVERIFIED",
                "excerpt": excerpt, "excerpt_sha256": digest(excerpt.encode()),
            }],
            "approval_authority": False, "issue_intake_authority": False,
            "forge_dispatch_authority": False, "current_policy_authority": False,
        }

    def test_historical_source_integrity_binding_and_non_authority(self):
        history = self.history()
        result = self.gate(history=history)
        self.assertEqual(result["history_sha256"], digest(canonical(history).encode()))
        self.assertFalse(result["approval_authority"])
        item = self.entry(
            self.topic("approved"), "ANSWERED_BY_GITHUB_EVIDENCE",
            quote="Earlier discussion: notify only",
            answer="Historical statement", source="L-001")
        with self.assertRaisesRegex(ValueError, "current GitHub"):
            self.gate(history=history, proposals=self.proposal([item]))
        history["current_policy_authority"] = True
        with self.assertRaisesRegex(ValueError, "cannot assert current authority"):
            self.gate(history=history)
        history["current_policy_authority"] = False
        history["status"] = "SOURCE_CHANGED"
        with self.assertRaisesRegex(ValueError, "bound to current GitHub"):
            self.gate(history=history)

    def test_private_output_writes_exclusively(self):
        result = self.gate()
        with tempfile.TemporaryDirectory() as path:
            out = Path(path) / "candidate.json"
            write_private_report(out, result)
            self.assertEqual(out.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(out.read_text())["kind"],
                             "clarity-question-relevance-candidates")
            with self.assertRaises(FileExistsError):
                write_private_report(out, result)


if __name__ == "__main__":
    unittest.main()
