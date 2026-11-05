"""Trusted reconciliation regressions: synthetic artifacts, no model/network."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from evidence_context import canonical, digest
from question_freshness_attestation import attest_freshness, read_attestation_key
from question_relevance_research import build_prompt, research
from question_relevance_verify import build_challenge_prompt, challenge
from reconcile_question_evidence import main, reconcile
from recheck_github_sources import recheck, main as recheck_main
import test_question_relevance_verify as fixtures
from test_recheck_github_sources import FakeFreshGitHub

class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.IndependentQuestionChallengeTests()
        self.f.setUp()
        self.key = b"synthetic-collector-key-for-unit-tests-only"
        self.now = 1000
        self.history = None
        self.r = self.f.research_result
        self.make_challenge()
        self.readback = recheck(self.f.s, self.f.p, self.f.e, FakeFreshGitHub())
        self.sign()

    def make_challenge(self):
        prompt = build_challenge_prompt(self.f.prev, self.f.e, self.r, self.history)
        receipt = dict(self.f.receipt, prompt_sha256=digest(prompt.encode()))
        with patch("question_relevance_verify.run_model", return_value=(self.f.assessments, receipt)):
            self.c = challenge(self.f.s, self.f.p, self.f.e, self.f.report,
                               self.f.prev, self.f.hashes, self.r,
                               history=self.history, provider="claude")

    def sign(self):
        self.fresh = attest_freshness(self.readback, digest(canonical(self.c).encode()),
                                     self.key, 990, 995)

    def run_reconcile(self, **kwargs):
        values = dict(history=self.history, now=self.now)
        values.update(kwargs)
        with patch("subprocess.run", side_effect=AssertionError("No process/model allowed")):
            return reconcile(self.f.s, self.f.p, self.f.e, self.f.report,
                             self.f.prev, self.f.hashes, self.r, self.c,
                             self.fresh, self.key, **values)

    def test_reconciles_provenance_but_preserves_every_unresolved_question(self):
        out = self.run_reconcile()
        self.assertEqual(out["status"], "BLOCKED")
        self.assertEqual(out["source_status"], "AUTHENTICATED_MATCH_AT_READ_TIME")
        self.assertEqual(len(out["topics"]), 3)
        self.assertEqual(len(out["unresolved_topic_ids"]), 3)
        self.assertEqual(out["owner_question_candidate_ids"], [])
        self.assertEqual(out["counts"], {"SUPPORTED_ANSWER_CANDIDATE": 1,
                                        "NEEDS_RESEARCH": 1, "DUPLICATE_CANDIDATE": 1})
        for before, after in zip(self.f.prev["question_topics"], out["topics"]):
            for field in ("question", "topic_id", "original_question_ids", "source_ids", "proposed_by"):
                self.assertEqual(before[field], after[field])
            self.assertFalse(after["resolution_verified"])
        duplicate = next(t for t in out["topics"] if t["duplicate_of"])
        self.assertEqual(duplicate["duplicate_primary_status"], "NEEDS_RESEARCH")
        for key, value in out.items():
            if key.endswith("_authority") or key.endswith("_verified"):
                if key != "linear_history_authority":
                    self.assertIs(value, False)

    def test_dispute_and_material_owner_candidates_stay_blocked(self):
        self.f.assessments[0]["outcome"] = "DISPUTE"
        self.f.assessments[1].update(outcome="CONCUR", missing_evidence="")
        self.make_challenge()
        self.sign()
        out = self.run_reconcile()
        self.assertEqual(out["counts"]["DISPUTED"], 1)
        self.assertEqual(out["owner_question_candidate_ids"], [self.f.approval_id])
        self.assertFalse(out["inbox_import_authority"])

    def test_unsigned_wrong_key_and_tampered_collector_receipts_fail(self):
        original = copy.deepcopy(self.fresh)
        for value in (self.readback, {}, dict(original, hmac_sha256="0" * 64)):
            self.fresh = value
            with self.subTest(value=list(value)), self.assertRaises(ValueError):
                self.run_reconcile()
        self.fresh = original
        self.key = b"different-synthetic-collector-key-for-tests"
        with self.assertRaisesRegex(ValueError, "authentication"):
            self.run_reconcile()

    def test_receipt_age_and_future_times_fail_closed(self):
        for now in (989, 994, 1291):
            with self.subTest(now=now), self.assertRaisesRegex(ValueError, "expired"):
                self.run_reconcile(now=now)
        for age in (0, 901, True):
            with self.subTest(age=age), self.assertRaises(ValueError):
                self.run_reconcile(max_age_seconds=age)
        self.run_reconcile(now=1290)

    def test_changed_or_incomplete_sources_block_even_with_authentic_signature(self):
        baseline = copy.deepcopy(self.readback)
        mutations = [
            lambda r: r.update(recheck_status="SOURCE_CHANGED"),
            lambda r: r["rechecked_sources"].pop(),
            lambda r: r["rechecked_sources"].append(r["rechecked_sources"][0]),
            lambda r: r["rechecked_sources"][0].update(observed_revision="other"),
            lambda r: r["rechecked_sources"][0].update(content_matches=1),
            lambda r: r.update(evidence_sha256="0" * 64),
            lambda r: r.update(approval_authority=True),
            lambda r: r.update(target_issue="other/repository#169"),
        ]
        for mutation in mutations:
            self.readback = copy.deepcopy(baseline)
            mutation(self.readback)
            self.sign()
            with self.subTest(readback=self.readback), self.assertRaises(ValueError):
                self.run_reconcile()

    def test_challenge_replay_rejects_counts_sessions_prompt_and_authority(self):
        baseline = copy.deepcopy(self.c)
        mutations = [
            lambda c: c["counts"].update(CONCUR=99),
            lambda c: c["model_receipt"].update(prompt_sha256="0" * 64),
            lambda c: c["model_receipt"].update(session_id=self.r["receipt"]["session_id"]),
            lambda c: c["model_receipt"].update(model_resolved="unrelated"),
            lambda c: c.update(approval_authority=True),
            lambda c: c.update(research_proposal_sha256="0" * 64),
            lambda c: c["assessments"].pop(),
            lambda c: c["assessments"][0]["source_quotes"][0].update(quote="Invented quote not in source"),
            lambda c: c["assessments"][0].update(missing_evidence="Still missing required evidence"),
        ]
        for mutate in mutations:
            self.c = copy.deepcopy(baseline)
            mutate(self.c)
            self.sign()
            with self.subTest(challenge=self.c), self.assertRaises(ValueError):
                self.run_reconcile()

    def test_signature_cannot_be_replayed_for_another_valid_challenge(self):
        self.c["assessments"][0]["rationale"] += " More context."
        with self.assertRaisesRegex(ValueError, "exact challenge"):
            self.run_reconcile()

    def test_forged_preview_and_research_rejected(self):
        self.f.prev["question_topics"][0]["question"] = "Changed question?"
        with self.assertRaises(ValueError):
            self.run_reconcile()

    def test_partial_batch_retains_unresearched_questions(self):
        start = next(i for i, t in enumerate(self.f.prev["question_topics"])
                     if t["topic_id"] == self.f.doc_id)
        prompt, ids = build_prompt(self.f.prev, self.f.e, None, start=start, count=1)
        decisions = [d for d in self.r["proposals"]["decisions"] if d["topic_id"] in ids]
        receipt = dict(self.r["receipt"], question_count=1, prompt_sha256=digest(prompt.encode()))
        with patch("question_relevance_research.run_claude_research", return_value=(decisions, receipt)):
            self.r = research(self.f.s, self.f.p, self.f.e, self.f.report,
                              self.f.prev, self.f.hashes, start=start, count=1, provider="claude")
        self.f.assessments = [a for a in self.f.assessments if a["topic_id"] in ids]
        self.f.receipt["question_count"] = 1
        self.make_challenge()
        self.sign()
        out = self.run_reconcile()
        self.assertEqual(len(out["topics"]), 3)
        self.assertEqual(out["counts"]["NOT_YET_RESEARCHED"], 2)

    def test_linear_history_remains_context_and_cannot_supply_factual_resolution(self):
        self.history = self.f.case.history()
        prompt, _ = build_prompt(self.f.prev, self.f.e, self.history, count=3)
        self.r["receipt"]["prompt_sha256"] = digest(prompt.encode())
        self.make_challenge()
        self.sign()
        out = self.run_reconcile()
        self.assertEqual(out["linear_history_authority"], "HISTORICAL_UNVERIFIED")
        fact = next(d for d in self.r["proposals"]["decisions"] if d["topic_id"] == self.f.doc_id)
        fact["evidence"] = [{"source_id": "L-001", "quote": "Earlier discussion: notify only"}]
        with self.assertRaisesRegex(ValueError, "current GitHub"):
            self.run_reconcile()

    def test_history_authority_and_linear_intake_are_rejected(self):
        self.history = self.f.case.history()
        self.history["current_policy_authority"] = True
        with self.assertRaises(ValueError):
            self.run_reconcile()
        self.history = None
        self.f.s["source_issue_id"] = "HIST-101"
        with self.assertRaises(ValueError):
            self.run_reconcile()

    def test_collector_cli_signs_own_readback_and_private_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            values = {"story": self.f.s, "policy": self.f.p,
                      "github-evidence": self.f.e, "challenge": self.c}
            argv = ["recheck"]
            for name, value in values.items():
                path = root / (name + ".json")
                path.write_text(json.dumps(value))
                path.chmod(0o600)
                argv += ["--" + name, str(path)]
            keypath = root / "collector.key"
            keypath.write_bytes(self.key)
            keypath.chmod(0o600)
            tokenpath = root / "github.key"
            tokenpath.write_text("synthetic-token-not-a-live-credential")
            tokenpath.chmod(0o600)
            output = root / "signed.json"
            argv += ["--github-key-file", str(tokenpath), "--attestation-key-file", str(keypath),
                     "--output", str(output)]
            with patch("sys.argv", argv), patch("recheck_github_sources.GitHubFreshnessClient",
                                                return_value=FakeFreshGitHub()):
                self.assertEqual(recheck_main(), 0)
            signed = json.loads(output.read_text())
            self.assertIn("hmac_sha256", signed)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(self.key.decode(), output.read_text())
            self.assertEqual(read_attestation_key(keypath), self.key)
            keypath.chmod(0o644)
            with self.assertRaises(ValueError):
                read_attestation_key(keypath)

    def test_cli_fails_without_creating_output_on_invalid_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bad = root / "bad.json"
            bad.write_text("{}")
            bad.chmod(0o600)
            output = root / "out.json"
            argv = ["reconcile"]
            for name in ("story", "policy", "github-evidence", "review", "preview", "research",
                         "challenge", "freshness", "collector-key-file"):
                argv += ["--" + name, str(bad)]
            argv += ["--output", str(output)]
            with patch("sys.argv", argv):
                self.assertEqual(main(), 3)
            self.assertFalse(output.exists())

    def test_cli_outputs_private_blocked_report_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            values = {"story": self.f.s, "policy": self.f.p, "github-evidence": self.f.e,
                      "review": self.f.report, "preview": self.f.prev, "research": self.r,
                      "challenge": self.c, "freshness": self.fresh}
            argv = ["reconcile"]
            for name, value in values.items():
                path = root / (name + ".json")
                path.write_text(json.dumps(value, sort_keys=True))
                path.chmod(0o600)
                argv += ["--" + name, str(path)]
            keypath = root / "collector.key"
            keypath.write_bytes(self.key)
            keypath.chmod(0o600)
            output = root / "report.json"
            argv += ["--collector-key-file", str(keypath), "--output", str(output)]
            with patch("sys.argv", argv), patch("question_freshness_attestation.time.time", return_value=self.now), \
                    patch("subprocess.run", side_effect=AssertionError("No models")):
                self.assertEqual(main(), 0)
                before = output.read_bytes()
                self.assertEqual(main(), 3)
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(before)["status"], "BLOCKED")
            self.assertNotIn(self.key.decode(), before.decode())


if __name__ == "__main__":
    unittest.main()
