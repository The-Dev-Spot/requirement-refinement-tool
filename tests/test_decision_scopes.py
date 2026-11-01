"""Synthetic opt-in decision-scope regression; no paid model calls."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from quality_review import prompt_for, verify_inputs, summarize


def story():
    return {"title": "Supervised Remote Control pilot",
            "story_type": "non-behavioral",
            "review_scope": "PILOT_RC",
            "payload": "Operator Start is mandatory for this pilot only.",
            "criteria": ["Operator authorizes one disposable session."]}


def policy():
    return {
        "project": "Synthetic Forge City", "adopted": False,
        "risk_register_status": "DRAFT",
        "decisions": [],
        "review_scope": "PILOT_RC",
        "decision_register": [
            {"id": "OLD_PILOT", "scope": "PILOT_RC", "status": "HISTORICAL",
             "source": "HOM-1972 archived", "revision": "r1", "authority": "unsworn proposal",
             "text": "The pilot has a maximum of two containers.", "supersedes": []},
            {"id": "PILOT_A", "scope": "PILOT_RC", "status": "ACTIVE",
             "source": "HOM-1972 current", "revision": "r2", "authority": "owner-decision-claim",
             "text": "One interactive job with operator Start.", "supersedes": ["OLD_PILOT"]},
            {"id": "TARGET_AUTO", "scope": "TARGET_AUTO", "status": "ACTIVE",
             "source": "HOM-1979", "revision": "r4", "authority": "owner-decision-claim",
             "text": "No fresh human Start for every admitted issue.", "supersedes": []},
            {"id": "TARGET_CAP", "scope": "TARGET_CAPACITY", "status": "ACTIVE",
             "source": "HOM-1973", "revision": "r3", "authority": "owner-decision-claim",
             "text": "Four worker slots across two independent pools.", "supersedes": []}
        ]
    }


class ScopedDecisionTests(unittest.TestCase):
    def test_legacy_unchanged(self):
        s = story()
        del s["review_scope"]
        p = policy()
        del p["review_scope"], p["decision_register"]
        p["decisions"] = [{"id": "D1", "source": "owner note", "revision": "1",
                           "authority": "owner", "text": "One job"}]
        verify_inputs(s, p)

    def test_manual_and_auto_can_coexist_in_separate_scopes(self):
        s, p = story(), policy()
        verify_inputs(s, p)
        for stage in ("investigator", "evaluator", "challenger"):
            prompt = prompt_for(stage, s, p)
            self.assertIn("SCOPED DECISION PROVENANCE", prompt)
            self.assertIn("Never infer supersession solely", prompt)
            self.assertIn("PILOT_RC", prompt)
            self.assertIn("TARGET_AUTO", prompt)

    def test_scope_mismatch_or_missing_register_fails_closed(self):
        s, p = story(), policy()
        p["review_scope"] = "TARGET_AUTO"
        with self.assertRaisesRegex(ValueError, "matching explicit"):
            verify_inputs(s, p)
        p = policy()
        del p["decision_register"]
        with self.assertRaisesRegex(ValueError, "1..50"):
            verify_inputs(s, p)

    def test_cross_scope_supersession_is_invalid(self):
        s, p = story(), policy()
        p["decision_register"][1]["supersedes"] = ["TARGET_AUTO"]
        with self.assertRaisesRegex(ValueError, "Cross-scope"):
            verify_inputs(s, p)

    def test_cannot_supersede_an_active_decision(self):
        s, p = story(), policy()
        p["decision_register"][0]["status"] = "ACTIVE"
        with self.assertRaisesRegex(ValueError, "HISTORICAL"):
            verify_inputs(s, p)

    def test_unknown_duplicate_and_unverifiable_scopes_refused(self):
        s, p = story(), policy()
        p["decision_register"][1]["id"] = "OLD_PILOT"
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            verify_inputs(s, p)
        p = policy()
        p["decision_register"][1]["scope"] = "PILOT_Rc"
        with self.assertRaisesRegex(ValueError, "Invalid scoped decision scope"):
            verify_inputs(s, p)
        p = policy()
        p["decision_register"][1]["status"] = "PENDING"
        p["decision_register"][1]["supersedes"] = []
        with self.assertRaisesRegex(ValueError, "ACTIVE source"):
            verify_inputs(s, p)

    def test_unlabeled_legacy_decisions_cannot_mix_with_scoped_register(self):
        s, p = story(), policy()
        p["decisions"] = [{"id": "D", "source": "unlabeled", "revision": "r1",
                           "authority": "unknown", "text": "One model slot"}]
        with self.assertRaisesRegex(ValueError, "Do not mix"):
            verify_inputs(s, p)

    def test_pending_in_scope_must_block_clean_candidate(self):
        s, p = story(), policy()
        p["decision_register"].append({
            "id": "TERMS_OPEN", "scope": "PILOT_RC", "status": "PENDING",
            "source": "HOM-1972", "revision": "r2", "authority": "not-verified",
            "text": "Provider terms qualification pending.", "supersedes": []
        })
        verify_inputs(s, p)
        lint = {"kind": "clarity-deterministic-quality-report", "status": "PASS",
                "open_question_count": 0}
        report = summarize(lint, {}, p, "claude")
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("unresolved scoped decision TERMS_OPEN", report["reasons"])
        self.assertFalse(report["ready_for_handover"])


if __name__ == "__main__":
    unittest.main()
