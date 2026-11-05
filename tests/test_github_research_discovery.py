"""Scoped discovery regressions: synthetic GitHub responses, no network/model."""
import base64
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from discover_github_research import GitHubResearchClient, discover, main, validate_plan

REPO = "example-org/project"
HEAD, TREE = "a" * 40, "b" * 40
TIME = "2026-11-05T10:00:00Z"


def inputs():
    story = {"source_issue_id": REPO + "#12", "review_scope": "APP_REVIEW"}
    policy = {"review_scope": "APP_REVIEW", "evidence_allowed_repositories": [REPO]}
    plan = {"schema_version": 1, "target_issue": story["source_issue_id"], "review_scope": "APP_REVIEW",
            "repository": REPO, "document_prefixes": ["docs/adr"], "terms": ["manual approval"]}
    return plan, story, policy


class FakeGitHub(GitHubResearchClient):
    def __init__(self):
        self.calls = []
        self.nodes = [{"path": "docs/adr/0001.md", "mode": "100644", "type": "blob", "sha": "c" * 40},
                      {"path": "outside/private.md", "mode": "100644", "type": "blob", "sha": "d" * 40}]
        self.text = "# ADR 1\n\nPrior discussion of manual approval. Proposed, not ratified.\n"
        self.search = {"total_count": 1, "incomplete_results": False,
                       "items": [{"number": 7, "html_url": "https://github.com/%s/pull/7" % REPO,
                                  "pull_request": {"url": "unused"}}]}
        self.pr = {"number": 7, "html_url": "https://github.com/%s/pull/7" % REPO,
                   "title": "Manual approval implementation", "body": "Historical proposal.",
                   "updated_at": TIME, "state": "closed", "merged": True, "draft": False,
                   "base": {"sha": HEAD, "repo": {"full_name": REPO}},
                   "head": {"sha": "d" * 40, "repo": {"full_name": "another-org/fork"}}}
        self.target = {"number": 12, "html_url": "https://github.com/%s/issues/12" % REPO,
                       "title": "Current GitHub requirement", "body": "Review the change.",
                       "updated_at": TIME, "comments": 0, "state": "open"}
        self.truncated = False
        self.move = False
        self.change_pr = False
        self.change_target = False

    def _get(self, path, query=None):
        self.calls.append((path, query))
        prefix = "/repos/" + REPO
        if path == prefix:
            return {"default_branch": "main"}
        if path == prefix + "/issues/12":
            value = copy.deepcopy(self.target)
            if self.change_target and sum(p == path for p, _ in self.calls) > 1:
                value["body"] += " Changed requirement."
            return value
        if path == prefix + "/commits/main":
            return {"sha": "f" * 40 if self.move and sum(p == path for p, _ in self.calls) > 1 else HEAD}
        if path == prefix + "/git/commits/" + HEAD:
            return {"sha": HEAD, "tree": {"sha": TREE}}
        if path == prefix + "/git/trees/" + TREE:
            return {"sha": TREE, "truncated": self.truncated, "tree": copy.deepcopy(self.nodes)}
        if path == prefix + "/contents/docs/adr/0001.md":
            assert query == {"ref": HEAD}
            return {"type": "file", "encoding": "base64", "content": base64.b64encode(self.text.encode()).decode(),
                    "size": len(self.text.encode())}
        if path == "/search/issues":
            return copy.deepcopy(self.search)
        if path == prefix + "/pulls/7":
            value = copy.deepcopy(self.pr)
            if self.change_pr and sum(p == path for p, _ in self.calls) > 1:
                value["body"] += " Superseded."
            return value
        raise AssertionError("Unexpected endpoint: " + path)


class ResearchDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.story, self.policy = inputs()
        self.github = FakeGitHub()

    def discover(self):
        return discover(self.plan, self.story, self.policy, self.github)

    def test_discovers_pinned_documents_and_pr_lifecycle_as_candidates_only(self):
        result = self.discover()
        self.assertEqual(result["status"], "CANDIDATES_ONLY")
        self.assertEqual(result["target_issue_revision"], TIME)
        self.assertEqual(result["documents_scanned"], 1)
        self.assertEqual([c["source_kind"] for c in result["candidates"]], ["DOCUMENT", "PULL_REQUEST"])
        self.assertIn(HEAD, result["candidates"][0]["url"])
        self.assertTrue(result["candidates"][1]["lifecycle"]["merged"])
        for item in result["candidates"]:
            self.assertFalse(item["selected_for_review"])
            self.assertEqual(item["authority"], "UNVERIFIED")
        for key in result:
            if key.endswith("_authority"):
                self.assertIs(result[key], False)
        self.assertFalse(any("outside/private" in path for path, _ in self.github.calls))

    def test_search_query_is_repository_bound_and_literal(self):
        self.discover()
        query = next(q for p, q in self.github.calls if p == "/search/issues")
        self.assertEqual(query["q"], 'repo:example-org/project is:pr in:title,body "manual approval"')
        self.assertEqual(query["per_page"], 9)

    def test_empty_results_do_not_prove_absence_or_owner_materiality(self):
        self.github.search = {"total_count": 0, "incomplete_results": False, "items": []}
        self.github.text = "# Unrelated documentation.\n"
        result = self.discover()
        self.assertEqual(result["candidates"], [])
        self.assertFalse(result["search_completeness_authority"])
        self.assertFalse(result["approval_authority"])

    def test_invalid_query_terms_scope_paths_and_linear_targets_fail_before_reads(self):
        for mutate in (lambda p: p.update(target_issue="HIST-1"),
                       lambda p: p.update(repository="outside/project"),
                       lambda p: p.update(review_scope="OTHER"),
                       lambda p: p.update(terms=['x repo:outside/project']),
                       lambda p: p.update(terms=['term" OR another']),
                       lambda p: p.update(terms=["manual approval", "MANUAL APPROVAL"]),
                       lambda p: p.update(document_prefixes=["docs/../secrets"])):
            plan = copy.deepcopy(self.plan)
            mutate(plan)
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                discover(plan, self.story, self.policy, self.github)
        self.assertEqual(self.github.calls, [])

    def test_target_pull_request_cannot_become_issue_intake(self):
        self.github.target["pull_request"] = {}
        with self.assertRaisesRegex(ValueError, "pull request"):
            self.discover()

    def test_incomplete_tree_and_symlink_documents_are_rejected(self):
        self.github.truncated = True
        with self.assertRaisesRegex(ValueError, "tree incomplete"):
            self.discover()
        self.github.truncated = False
        for mode in ("120000", "100755"):
            self.github.nodes[0]["mode"] = mode
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "regular Markdown"):
                self.discover()

    def test_document_selection_overflow_fails_before_file_reads(self):
        self.github.nodes = [dict(self.github.nodes[0], path="docs/adr/%d.md" % i) for i in range(9)]
        with self.assertRaisesRegex(ValueError, "too broad"):
            self.discover()
        self.assertFalse(any("/contents/" in p for p, _ in self.github.calls))

    def test_search_incomplete_overflow_and_foreign_results_are_rejected(self):
        original = copy.deepcopy(self.github.search)
        for mutate in (lambda s: s.update(incomplete_results=True),
                       lambda s: s.update(total_count=9),
                       lambda s: s.update(total_count=True),
                       lambda s: s["items"][0].update(html_url="https://github.com/another/repo/pull/7"),
                       lambda s: s["items"][0].pop("pull_request")):
            self.github.search = copy.deepcopy(original)
            mutate(self.github.search)
            with self.subTest(search=self.github.search), self.assertRaises(ValueError):
                self.discover()

    def test_changed_pr_head_default_branch_and_issue_block_discovery(self):
        for flag in ("change_pr", "move", "change_target"):
            self.github = FakeGitHub()
            setattr(self.github, flag, True)
            with self.subTest(flag=flag), self.assertRaisesRegex(ValueError, "changed"):
                self.discover()

    def test_pr_lifecycle_repository_and_pin_must_be_valid(self):
        original = copy.deepcopy(self.github.pr)
        for mutate in (lambda p: p.update(state="open"),
                       lambda p: p.update(draft=True),
                       lambda p: p["base"]["repo"].update(full_name="outside/project"),
                       lambda p: p["head"].update(sha="main")):
            self.github.pr = copy.deepcopy(original)
            mutate(self.github.pr)
            with self.subTest(pr=self.github.pr), self.assertRaises(ValueError):
                self.discover()

    def test_pr_search_index_mismatch_requires_recollection(self):
        self.github.pr.update(title="Unrelated old title", body="Unrelated old body")
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.discover()

    def test_obvious_credentials_never_enter_output(self):
        self.github.text += " github_pat_" + "a" * 35
        with self.assertRaisesRegex(ValueError, "credential"):
            self.discover()

    def test_cli_writes_only_private_candidate_output_without_models(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            argv = ["discovery"]
            for name, value in (("plan", self.plan), ("story", self.story), ("policy", self.policy)):
                path = root / (name + ".json")
                path.write_text(json.dumps(value))
                argv += ["--" + name, str(path)]
            key = root / "github.key"
            key.write_text("synthetic-read-only-key-for-test")
            key.chmod(0o600)
            output = root / "candidates.json"
            argv += ["--github-key-file", str(key), "--output", str(output)]
            with patch("sys.argv", argv), patch("discover_github_research.GitHubResearchClient", return_value=self.github), \
                    patch("subprocess.run", side_effect=AssertionError("No model calls")):
                self.assertEqual(main(), 0)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(key.read_text(), output.read_text())
            with patch("sys.argv", argv), patch("discover_github_research.GitHubResearchClient", return_value=self.github):
                self.assertEqual(main(), 3)


if __name__ == "__main__":
    unittest.main()
