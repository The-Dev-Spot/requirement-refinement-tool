"""Mocked GitHub current-read freshness checks; no live network or keys."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from collect_github_context import collect
from recheck_github_sources import GitHubFreshnessClient, recheck
from test_github_context import FakeGitHub, plan, policy, story, SHA


class FakeFreshGitHub(FakeGitHub):
    def __init__(self, *, branch="main", moved=False, missing_content=False,
                 issue_time_changed=False, concurrent=False):
        super().__init__(change_on_recheck=concurrent)
        self.branch = branch
        self.moved = moved
        self.missing_content = missing_content
        self.issue_time_changed = issue_time_changed
        self.commits_seen = 0

    def default_branch(self, repository):
        self.calls.append(("default_branch", repository))
        return self.branch

    def commit(self, repo, ref):
        self.commits_seen += 1
        old = super().commit(repo, ref)
        return "b" * 40 if self.moved else old

    def file(self, repo, path, sha):
        if self.missing_content:
            return "# Unrelated file. No longer matches pinned excerpt.\n"
        return super().file(repo, path, sha)

    def issue(self, repo, number):
        data = super().issue(repo, number)
        if self.issue_time_changed:
            data["updated_at"] = "2026-11-04T09:00:00Z"
        return data


class GitHubFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.story = story()
        self.policy = policy()
        self.evidence = collect(plan(), self.story, self.policy, FakeGitHub())
        self.assertEqual(len(self.evidence["sources"]), 2)

    def test_current_source_readback_only_confirms_snapshots(self):
        result = recheck(self.story, self.policy, self.evidence, FakeFreshGitHub())
        self.assertEqual(result["recheck_status"], "MATCHED_AT_READ_TIME")
        self.assertEqual([s["status"] for s in result["rechecked_sources"]],
                         ["MATCHED", "MATCHED"])
        self.assertTrue(result["github_network_rechecked"])
        for name in ("owner_policy_authority_verified",
                     "semantic_answer_sufficiency_verified",
                     "automatic_question_suppression_authority",
                     "inbox_import_authority", "approval_authority",
                     "forge_dispatch_authority"):
            self.assertFalse(result[name])

    def test_issue_revision_change_is_not_fresh(self):
        result = recheck(
            self.story, self.policy, self.evidence,
            FakeFreshGitHub(issue_time_changed=True))
        self.assertEqual(result["recheck_status"], "SOURCE_CHANGED")
        self.assertEqual(result["rechecked_sources"][0]["status"], "SOURCE_CHANGED")

    def test_repo_branch_moved_even_if_pinned_file_still_readable(self):
        result = recheck(self.story, self.policy, self.evidence,
                         FakeFreshGitHub(moved=True))
        self.assertEqual(result["recheck_status"], "SOURCE_CHANGED")
        self.assertTrue(result["rechecked_sources"][1]["content_matches"])
        self.assertEqual(result["rechecked_sources"][1]["status"], "SOURCE_CHANGED")

    def test_source_quote_removed_marks_changed(self):
        result = recheck(self.story, self.policy, self.evidence,
                         FakeFreshGitHub(missing_content=True))
        self.assertEqual(result["recheck_status"], "SOURCE_CHANGED")
        self.assertFalse(result["rechecked_sources"][1]["content_matches"])

    def test_changed_issue_during_read_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "changed during"):
            recheck(self.story, self.policy, self.evidence,
                    FakeFreshGitHub(concurrent=True))

    def test_github_source_is_bound_to_allowlisted_original_story(self):
        changed = copy.deepcopy(self.evidence)
        changed["target_issue"] = "someone/else#10"
        with self.assertRaises(ValueError):
            recheck(self.story, self.policy, changed, FakeFreshGitHub())
        changed = copy.deepcopy(self.evidence)
        changed["sources"][1]["excerpt"] = "Invented source line."
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            recheck(self.story, self.policy, changed, FakeFreshGitHub())

    def test_repo_default_branch_metadata_is_validated(self):
        obj = object.__new__(GitHubFreshnessClient)
        for value in ("", "../danger", "main//bad", "main?x", "not a branch"):
            with patch.object(obj, "_get", return_value={"default_branch": value}):
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, "branch"):
                    obj.default_branch("example-owner/example-repo")
        with patch.object(obj, "_get", return_value={"default_branch": "main"}):
            self.assertEqual(obj.default_branch("example-owner/example-repo"), "main")


if __name__ == "__main__":
    unittest.main()
