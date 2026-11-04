"""No-network safety contract for operator-scoped historical Linear reading."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from collect_linear_history import collect_history, validate_plan
from collect_context import write_private


def inputs():
    story = {"source_issue_id": "example-org/sample-repo#123",
             "review_scope": "APP_REVIEW"}
    policy = {"review_scope": "APP_REVIEW",
              "evidence_allowed_repositories": ["example-org/sample-repo"],
              "adopted": False}
    plan = {
        "schema_version": 1,
        "target_issue": story["source_issue_id"],
        "review_scope": "APP_REVIEW",
        "workspace": "example-workspace",
        "allowed_issue_prefixes": ["HIST"],
        "historical_issues": [
            {"id": "HIST-101", "scope": "APP_REVIEW", "focus": "prior decision"},
            {"id": "HIST-102", "scope": "APP_REVIEW", "focus": "prior decision"},
        ],
    }
    return plan, story, policy


class FakeHistory:
    def __init__(self, changed=False, secret=False):
        self.calls = []
        self.changed = changed
        self.secret = secret

    def issue(self, iid):
        self.calls.append(iid)
        description = ("prior decision: manually approve all deployments; "
                       "this historical record must be rechecked")
        if self.secret:
            description += " github_pat_" + "a" * 35
        rev = "2026-10-01T08:15:00Z"
        if self.changed and self.calls.count(iid) > 1:
            rev = "2026-10-01T08:15:01Z"
        return {
            "identifier": iid,
            "title": "Previous architecture discussion",
            "description": description,
            "updatedAt": rev,
        }


class LinearHistoricalReadTests(unittest.TestCase):
    def test_linear_history_cannot_be_intake_or_authorization(self):
        plan, story, policy = inputs()
        fake = FakeHistory()
        result = collect_history(plan, story, policy, fake)
        self.assertEqual(fake.calls, ["HIST-101", "HIST-102",
                                      "HIST-101", "HIST-102"])
        self.assertEqual(result["target_issue"], "example-org/sample-repo#123")
        self.assertEqual(result["status"], "SOURCE_UNVERIFIED")
        self.assertEqual(len(result["historical_sources"]), 2)
        self.assertFalse(result["approval_authority"])
        self.assertFalse(result["issue_intake_authority"])
        self.assertFalse(result["current_policy_authority"])
        self.assertFalse(result["forge_dispatch_authority"])
        for item in result["historical_sources"]:
            self.assertEqual(item["authority"], "HISTORICAL_UNVERIFIED")
            self.assertEqual(item["project_mapping"], "OPERATOR_SELECTED_UNVERIFIED")
            self.assertTrue(item["url"].startswith("https://linear.app/"))
            self.assertNotIn("Bearer", item["excerpt"])
        self.assertNotIn("issues", result)
        self.assertNotIn("acceptance", result)

    def test_plan_rejects_linear_target_and_unmapped_github_project(self):
        plan, story, policy = inputs()
        for target in ["HIST-101", "example-org/other-repo#123"]:
            bad = dict(plan, target_issue=target)
            with self.subTest(target=target), self.assertRaises(ValueError):
                validate_plan(bad, story, policy)
        policy["evidence_allowed_repositories"] = ["example-org/other-repo"]
        with self.assertRaisesRegex(ValueError, "allowlisted"):
            validate_plan(plan, story, policy)

    def test_plan_rejects_unsanctioned_linear_projects_and_scopes(self):
        plan, story, policy = inputs()
        for change in (
            {"allowed_issue_prefixes": ["OPS"]},
            {"allowed_issue_prefixes": ["HIST", "HIST"]},
            {"historical_issues": [{"id": "FOO-19", "scope": "APP_REVIEW",
                                    "focus": "previous work"}]},
            {"historical_issues": [{"id": "HIST-101", "scope": "OTHER",
                                    "focus": "prior decision"}]},
            {"historical_issues": plan["historical_issues"] * 7},
            {"review_scope": "OTHER"},
            {"workspace": "https://linear.app"},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_plan(dict(plan, **change), story, policy)

    def test_detects_historical_source_change_without_accepting_it(self):
        plan, story, policy = inputs()
        result = collect_history(plan, story, policy, FakeHistory(changed=True))
        self.assertEqual(result["status"], "SOURCE_CHANGED")
        self.assertFalse(result["approval_authority"])

    def test_redacts_obvious_tokens_by_failing_before_packet_creation(self):
        plan, story, policy = inputs()
        with self.assertRaisesRegex(ValueError, "credential"):
            collect_history(plan, story, policy, FakeHistory(secret=True))

    def test_private_packet_cannot_be_overwritten(self):
        plan, story, policy = inputs()
        result = collect_history(plan, story, policy, FakeHistory())
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "history"
            directory.mkdir(mode=0o700)
            dest = directory / "history.json"
            write_private(dest, result)
            self.assertEqual(dest.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(dest.read_text())["kind"],
                             "clarity-linear-history-context")
            with self.assertRaises(FileExistsError):
                write_private(dest, result)


if __name__ == "__main__":
    unittest.main()
