"""Synthetic question-export contract tests. No Slack, API or paid models."""
import copy
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from export_review_questions import extract_proposals, read_private_report


def report():
    hashes = {"input_file_sha256": "a" * 64, "policy_file_sha256": "b" * 64,
              "rubric_file_sha256": "c" * 64}
    results = {}
    receipts = {}
    for index, stage in enumerate(("investigator", "evaluator", "challenger")):
        questions = ["Which approved source is authoritative?"]
        if index == 1:
            questions.append("What is the quota pause behavior?")
        if index == 2:
            questions = ["  WHICH approved source  is authoritative? "]
        results[stage] = {"stage": stage, "verdict": "FAIL",
                          "questions": questions}
        receipts[stage] = {"model_verified": True,
                           "session_id": f"provider-session-{index}"}
    return {"schema_version": 1, "kind": "clarity-independent-review",
            **hashes,
            "run": {"results": results, "receipts": receipts,
                    "aggregate": {"status": "BLOCKED"}}}


class QuestionExportTests(unittest.TestCase):
    def test_dedup_across_three_stages_and_safe_notification(self):
        batch, event = extract_proposals(report())
        self.assertEqual(len(batch["questions"]), 2)
        self.assertEqual(event["question_count"], 2)
        self.assertEqual(batch["state"], "NEEDS_INFORMATION")
        self.assertFalse(batch["approval_authority"])
        self.assertFalse(event["forge_dispatch_authority"])
        self.assertTrue(event["needs_trusted_source_binding"])
        source = next(q for q in batch["questions"] if "source" in q["question"])
        self.assertEqual(source["proposed_by"], ["investigator", "challenger"])
        for word in ("authoritative?", "provider-session-", "raw_envelope", "model_usage", "login"):
            self.assertNotIn(word, json.dumps(event))
        self.assertEqual(event["event_id"], extract_proposals(report())[1]["event_id"])

    def test_blocked_without_questions_is_not_marked_ready(self):
        r = report()
        for stage in r["run"]["results"].values():
            stage["questions"] = []
        batch, event = extract_proposals(r)
        self.assertEqual(event["state"], "REVIEW_BLOCKED_WITHOUT_QUESTIONS")
        self.assertEqual(batch["questions"], [])
        self.assertFalse(event["approval_authority"])

    def test_candidate_without_questions_still_no_acceptance(self):
        r = report()
        r["run"]["aggregate"]["status"] = "REVIEWABLE_CANDIDATE"
        for stage in r["run"]["results"].values():
            stage["questions"] = []
        batch, event = extract_proposals(r)
        self.assertEqual(event["state"], "NO_QUESTIONS")
        self.assertFalse(batch["forge_dispatch_authority"])

    def test_provider_not_verified_or_receipt_missing_rejected(self):
        r = report()
        r["run"]["receipts"]["investigator"]["model_verified"] = False
        with self.assertRaisesRegex(ValueError, "validated model"):
            extract_proposals(r)
        r = report()
        del r["run"]["receipts"]["challenger"]
        with self.assertRaisesRegex(ValueError, "validated model"):
            extract_proposals(r)

    def test_malformed_hash_question_or_stage_rejected(self):
        r = report()
        r["input_file_sha256"] = "NOT-A-SHA"
        with self.assertRaisesRegex(ValueError, "input_file_sha256"):
            extract_proposals(r)
        r = report()
        r["run"]["results"]["investigator"]["questions"] = [" "]
        with self.assertRaisesRegex(ValueError, "Invalid proposed question"):
            extract_proposals(r)
        r = report()
        r["run"]["results"]["investigator"]["stage"] = "evaluator"
        with self.assertRaisesRegex(ValueError, "validated model"):
            extract_proposals(r)

    def test_private_report_permissions_and_symlink_are_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base / "report.json"
            source.write_text(json.dumps(report()))
            source.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "group/world"):
                read_private_report(source)
            source.chmod(0o600)
            self.assertEqual(read_private_report(source)["kind"], "clarity-independent-review")
            alias = base / "link.json"
            alias.symlink_to(source)
            with self.assertRaisesRegex(ValueError, "non-symlinked"):
                read_private_report(alias)

    def test_cli_creates_private_files_without_network_or_authority(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source, private, outbox = [base / n for n in ("report.json", "questions.json", "event.json")]
            source.write_text(json.dumps(report()))
            source.chmod(0o600)
            script = Path(__file__).resolve().parents[1] / "scripts/export_review_questions.py"
            cmd = [sys.executable, str(script), "--report", str(source),
                   "--private-output", str(private), "--outbox-output", str(outbox)]
            finished = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            self.assertEqual(finished.returncode, 0, finished.stderr)
            self.assertIn("No notification, tracker write", finished.stdout)
            for dest in (private, outbox):
                self.assertEqual(stat.S_IMODE(dest.stat().st_mode), 0o600)
            self.assertEqual(json.loads(outbox.read_text())["question_count"], 2)
            self.assertNotIn("Which approved", outbox.read_text())
            again = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            self.assertNotEqual(again.returncode, 0)  # exclusive no-overwrite


if __name__ == "__main__":
    unittest.main()
