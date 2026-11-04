"""Offline checks for issue #37: examples are bounded, draft and non-authorizing."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from collect_github_context import validate_plan
from quality_review import verify_inputs
from decision_scopes import unresolved_scoped_decisions


def read(filename):
    return json.loads((ROOT / "examples" / filename).read_text(encoding="utf-8"))


class MediaIssue37PilotTests(unittest.TestCase):
    def setUp(self):
        self.plan = read("github-media-issue-37-evidence-plan.json")
        self.story = read("github-media-issue-37-story.json")
        self.policy = read("github-media-issue-37-policy-draft.json")

    def test_current_github_issue_only_with_bounded_repository_sources(self):
        verify_inputs(self.story, self.policy)
        validate_plan(self.plan, self.story, self.policy)
        self.assertEqual(self.plan["target_issue"], "The-Dev-Spot/homelab#37")
        self.assertEqual(len(self.plan["issues"]), 1)
        self.assertEqual(len(self.plan["files"]), 7)
        self.assertTrue(all(x["repository"] == "The-Dev-Spot/homelab"
                            for x in self.plan["issues"] + self.plan["files"]))
        self.assertEqual(self.plan["issues"][0]["number"], 37)
        self.assertTrue(all(x["scope"] == "MEDIA_UPDATES"
                            for x in self.plan["issues"] + self.plan["files"]))
        self.assertEqual(self.plan["schema_version"], 2)
        self.assertNotIn("linear", self.plan)

    def test_no_model_or_automation_can_confer_approval(self):
        self.assertFalse(self.policy["adopted"])
        self.assertFalse(self.policy["source_authority_verified"])
        self.assertFalse(self.policy["approve_forge"])
        self.assertEqual(self.policy["risk_register_status"], "DRAFT")
        self.assertTrue(unresolved_scoped_decisions(self.policy))
        self.assertEqual(self.story["story_type"], "non-behavioral")
        self.assertGreaterEqual(len(self.story["criteria"]), 3)
        self.assertLessEqual(len(self.story["criteria"]), 8)
        for rule in ("No Docker", "no bulk", "OWNER_DECISION_REQUIRED"):
            self.assertIn(rule, str(self.story) + str(self.policy))

    def test_policy_and_story_must_remain_scope_bound(self):
        self.policy["review_scope"] = "TARGET_AUTO"
        with self.assertRaisesRegex(ValueError, "matching explicit"):
            verify_inputs(self.story, self.policy)

    def test_no_silent_cross_repo_source_escalation(self):
        self.plan["files"][0]["repository"] = "The-Dev-Spot/forge"
        with self.assertRaisesRegex(ValueError, "Unauthorized"):
            validate_plan(self.plan, self.story, self.policy)


if __name__ == "__main__":
    unittest.main()
