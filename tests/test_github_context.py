"""GitHub Issues-only acceptance and collection tests: no live network or tokens."""
import base64
import copy
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from collect_github_context import (
    GitHubEvidenceClient, collect, validate_plan, issue_identity,
)
from evidence_context import canonical, digest, validate_evidence_packet
from quality_review import summarize, prompt_for

REPO = "The-Dev-Spot/homelab"
SHA = "a" * 40
URL = "https://github.com/The-Dev-Spot/homelab/issues/169"


def story():
    return {"source_issue_id": REPO + "#169",
            "review_scope": "PLATFORM_CONTROL",
            "title": "GitHub issues as source of truth",
            "story_type": "non-behavioral", "payload": "Issues go to GitHub"}


def policy():
    return {"review_scope": "PLATFORM_CONTROL",
            "evidence_allowed_repositories": [REPO],
            "project": "Synthetic", "decisions": [],
            "adopted": False, "risk_register_status": "DRAFT"}


def plan():
    return {"schema_version": 2, "target_issue": REPO + "#169",
            "issues": [{"repository": REPO, "number": 169,
                        "scope": "PLATFORM_CONTROL", "focus": "",
                        "include_comments": True}],
            "files": [{"repository": REPO, "ref": "main",
                       "path": "stacks/clarity-context-collector/README.md",
                       "scope": "PLATFORM_CONTROL", "kind": "DOCUMENT",
                       "focus": "GitHub"}]}


class FakeGitHub:
    def __init__(self, change_on_recheck=False):
        self.calls = []
        self.change_on_recheck = change_on_recheck
        self.reads = 0
        self.comments_seen = 0

    @staticmethod
    def canonical_issue_url(repo, number):
        return "https://github.com/%s/issues/%d" % (repo, number)

    def issue(self, repo, number):
        self.calls.append(("issue", repo, number))
        self.reads += 1
        when = ("2026-11-03T10:02:00Z"
                if self.change_on_recheck and self.reads > 2
                else "2026-11-03T10:00:00Z")
        return {"number": number, "html_url": self.canonical_issue_url(repo, number),
                "title": "Operational GitHub Issue",
                "body": "GitHub Issues are the source of truth; Linear is personal.",
                "comments": 1, "updated_at": when}

    def comments(self, repo, number, count):
        self.calls.append(("comments", repo, number))
        self.comments_seen += 1
        return [{"id": 101, "author": "example",
                 "body": "The collector must remain read only.",
                 "updated_at": "2026-11-03T10:00:00Z"}]

    def commit(self, repo, ref):
        self.calls.append(("commit", repo, ref))
        return SHA

    def file(self, repo, path, sha):
        self.calls.append(("file", repo, path, sha))
        return "# GitHub collector\nGitHub-only operational intake.\n"


class FakeHTTP:
    def __init__(self, result):
        self.result=result
        self.calls=[]

    def json(self, method, url, headers, payload=None):
        self.calls.append((method,url,payload))
        return self.result


class GitHubOnlyTests(unittest.TestCase):
    def test_github_issue_and_file_packet_is_valid_and_never_authoritative(self):
        client=FakeGitHub()
        packet=collect(plan(),story(),policy(),client)
        self.assertEqual(packet["schema_version"],2)
        self.assertEqual(packet["target_issue"],REPO+"#169")
        self.assertEqual(packet["freshness"],"SOURCE_UNVERIFIED")
        self.assertEqual(len(packet["sources"]),2)
        self.assertEqual(packet["sources"][0]["url"],URL)
        self.assertEqual(packet["sources"][0]["revision"],"2026-11-03T10:00:00Z")
        self.assertEqual(packet["sources"][0]["source_kind"],"ISSUE")
        self.assertEqual(packet["sources"][0]["authority_claim"],"UNVERIFIED")
        self.assertEqual(packet["sources"][1]["provider"],"github")
        self.assertIn("/blob/"+SHA+"/",packet["sources"][1]["url"])
        self.assertEqual(client.comments_seen,2)
        self.assertEqual(validate_evidence_packet(packet,story(),policy()),packet)
        self.assertTrue(all(source["provider"] == "github" for source in packet["sources"]))
        # Even a spotless model result never authorizes Forge.
        result=summarize({"status":"PASS"}, {}, policy(),
                         "fixtures", evidence_packet=packet)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertFalse(result["publication_authority"])
        for stage in ("investigator","evaluator","challenger"):
            text=prompt_for(stage,story(),policy(),evidence_packet=packet)
            self.assertIn("S-001",text)

    def test_github_revision_change_is_detected(self):
        packet=collect(plan(),story(),policy(),FakeGitHub(change_on_recheck=True))
        self.assertEqual(packet["freshness"],"SOURCE_CHANGED")

    def test_no_linear_sources_in_v2_even_with_matching_digests(self):
        packet=collect(plan(),story(),policy(),FakeGitHub())
        packet["sources"][0]["provider"]="linear"
        with self.assertRaisesRegex(ValueError,"GitHub sources only"):
            validate_evidence_packet(packet,story(),policy())

    def test_no_false_authority_from_issue_comment(self):
        packet=collect(plan(),story(),policy(),FakeGitHub())
        packet["sources"][0]["authority_claim"]="CLAIMED_ACTIVE"
        with self.assertRaisesRegex(ValueError,"cannot self-ratify"):
            validate_evidence_packet(packet,story(),policy())

    def test_reject_cross_repository_collisions_and_implicit_repos(self):
        candidate=plan()
        candidate["issues"][0]["repository"]="The-Dev-Spot/other"
        with self.assertRaisesRegex(ValueError,"Unauthorized"):
            validate_plan(candidate,story(),policy())
        candidate=plan()
        candidate["target_issue"]="The-Dev-Spot/other#169"
        with self.assertRaisesRegex(ValueError,"Canonical"):
            validate_plan(candidate,story(),policy())
        candidate=plan()
        candidate["issues"].append(copy.deepcopy(candidate["issues"][0]))
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            validate_plan(candidate,story(),policy())

    def test_reject_bad_schema_and_overlong_comment_history(self):
        candidate=plan()
        candidate["linear"]=[{"id":"HOM-1972"}]
        with self.assertRaisesRegex(ValueError,"exact fields"):
            validate_plan(candidate,story(),policy())
        candidate=plan()
        candidate["issues"][0]["number"]=True
        with self.assertRaisesRegex(ValueError,"Unauthorized"):
            validate_plan(candidate,story(),policy())
        raw={"number":169,"html_url":URL,"title":"Sample","body":"Body",
             "updated_at":"2026-11-03T10:00:00Z","comments":21}
        class Http:
            def json(self,*args,**kwargs):
                return raw
        client=GitHubEvidenceClient(Http(),"example-key")
        issue=client.issue(REPO,169)
        with self.assertRaisesRegex(ValueError,"Too many"):
            client.comments(REPO,169,issue["comments"])

    def test_github_client_reads_issue_comments_and_rejects_pr(self):
        item={"number":169,"html_url":URL,"title":"Sample","body":"Body",
              "updated_at":"2026-11-03T10:00:00Z","comments":1}
        http=FakeHTTP(item)
        client=GitHubEvidenceClient(http,"example-key")
        actual=client.issue(REPO,169)
        self.assertEqual(actual["title"],"Sample")
        self.assertEqual(http.calls[0][0],"GET")
        self.assertIn("/repos/The-Dev-Spot/homelab/issues/169",http.calls[0][1])
        item["pull_request"]={"url":"https://api.github.com/repos/x/y/pulls/169"}
        with self.assertRaisesRegex(ValueError,"pull request"):
            client.issue(REPO,169)
        comment={"id":17,"body":"Confirmed","updated_at":"2026-11-03T10:00:00Z",
                 "user":{"login":"tester"}}
        http=FakeHTTP([comment])
        client=GitHubEvidenceClient(http,"example-key")
        self.assertEqual(client.comments(REPO,169,1)[0]["author"],"tester")
        self.assertIn("/comments?per_page=21",http.calls[0][1])

    def test_old_v1_is_still_an_archive_schema(self):
        import test_evidence_context as prior
        archive=prior.pack()
        self.assertEqual(validate_evidence_packet(archive,prior.story(),
                                                  prior.policy()),archive)


if __name__=="__main__":
    unittest.main()
