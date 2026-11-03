"""Offline Clarity GitHub question triage tests; never call providers."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from collect_github_context import collect
from preview_github_review import prepare
from test_github_context import FakeGitHub, plan, story, policy
from test_review_question_export import report as example_report


def eligible_policy():
    obj = policy()
    obj["decision_register"] = [{
        "id": "TEST", "scope": "PLATFORM_CONTROL", "status": "ACTIVE",
        "source": "Synthetic", "revision": "v1",
        "authority": "UNVERIFIED", "text": "Not an adopted policy",
        "supersedes": []
    }]
    return obj


def bound_data(s, p, evidence):
    raw = tuple(json.dumps(x, sort_keys=True).encode() for x in (s, p, evidence))
    hashes = tuple(hashlib.sha256(x).hexdigest() for x in raw)
    report = example_report()
    report["input_file_sha256"], report["policy_file_sha256"], report["evidence_file_sha256"] = hashes
    return report, hashes


class GitHubTriageTest(unittest.TestCase):
    def test_draft_smoke_test_cannot_be_approved(self):
        s, p = story(), policy()
        evidence = collect(plan(), s, p, FakeGitHub())
        result = prepare(s, p, evidence)
        self.assertEqual(result["review_status"], "NOT_RUN")
        self.assertEqual(result["policy_review_contract"], "NOT_READY")
        self.assertFalse(result["inbox_import_authority"])
        self.assertFalse(result["forge_dispatch_authority"])
        self.assertEqual(result["topic_count"], 0)

    def test_legacy_packet_not_operational(self):
        import test_evidence_context as legacy
        with self.assertRaisesRegex(ValueError, "GitHub-only v2"):
            prepare(legacy.story(), legacy.policy(), legacy.pack())

    def test_review_questions_group_only_conservative_duplicates(self):
        s, p = story(), eligible_policy()
        evidence = collect(plan(), s, p, FakeGitHub())
        report, hashes = bound_data(s, p, evidence)
        report["run"]["results"]["investigator"]["questions"] = [
            "S-001: Who approved the start gate?",
            "What is the worker count?"
        ]
        report["run"]["results"]["evaluator"]["questions"] = [
            "S-001: Who approved the start gate!",
            "What is the worker count?"
        ]
        report["run"]["results"]["challenger"]["questions"] = [
            "S-001: Who approved the start gate?"
        ]
        result = prepare(s, p, evidence, report=report,
                         story_file_sha=hashes[0],
                         policy_file_sha=hashes[1],
                         evidence_file_sha=hashes[2])
        self.assertEqual(result["original_question_count"], 3)
        self.assertEqual(result["topic_count"], 2)
        first = next(q for q in result["question_topics"] if "start gate" in q["question"])
        self.assertEqual(len(first["original_question_ids"]), 2)
        self.assertEqual(first["source_ids"], ["S-001"])
        self.assertFalse(result["approval_authority"])

    def test_report_must_match_all_raw_input_hashes(self):
        s, p = story(), eligible_policy()
        evidence = collect(plan(), s, p, FakeGitHub())
        report, hashes = bound_data(s, p, evidence)
        report["evidence_file_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "exact private inputs"):
            prepare(s, p, evidence, report=report,
                    story_file_sha=hashes[0], policy_file_sha=hashes[1],
                    evidence_file_sha=hashes[2])

    def test_untrusted_reference_fails_closed(self):
        s, p = story(), eligible_policy()
        evidence = collect(plan(), s, p, FakeGitHub())
        report, hashes = bound_data(s, p, evidence)
        report["run"]["results"]["investigator"]["questions"] = ["S-099: Who signed?"]
        with self.assertRaisesRegex(ValueError, "unknown source citation"):
            prepare(s, p, evidence, report=report,
                    story_file_sha=hashes[0], policy_file_sha=hashes[1],
                    evidence_file_sha=hashes[2])

    def test_changed_issue_blocks_attached_review(self):
        s, p = story(), eligible_policy()
        evidence = collect(plan(), s, p, FakeGitHub(change_on_recheck=True))
        report, hashes = bound_data(s, p, evidence)
        self.assertEqual(prepare(s, p, evidence)["source_status"], "SOURCE_CHANGED")
        with self.assertRaisesRegex(ValueError, "Changed GitHub source"):
            prepare(s, p, evidence, report=report,
                    story_file_sha=hashes[0], policy_file_sha=hashes[1],
                    evidence_file_sha=hashes[2])

    def test_private_cli_without_review_creates_0600_preview(self):
        s, p = story(), policy()
        evidence = collect(plan(), s, p, FakeGitHub())
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            folder.chmod(0o700)
            for name, obj in (("story.json", s), ("policy.json", p),
                              ("evidence.json", evidence)):
                filename = folder / name
                filename.write_text(json.dumps(obj))
                filename.chmod(0o600)
            output = folder / "preview.json"
            script = Path(__file__).resolve().parents[1] / "scripts/preview_github_review.py"
            args = [sys.executable, str(script),
                    "--story", str(folder / "story.json"),
                    "--policy", str(folder / "policy.json"),
                    "--evidence", str(folder / "evidence.json"),
                    "--output", str(output)]
            import subprocess
            import stat
            done = subprocess.run(args, capture_output=True, text=True, timeout=10)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
            self.assertEqual(json.loads(output.read_text())["review_status"], "NOT_RUN")
            self.assertNotIn("Forge dispatch completed", done.stdout)
            replay = subprocess.run(args, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(replay.returncode, 0)


if __name__ == "__main__":
    unittest.main()
