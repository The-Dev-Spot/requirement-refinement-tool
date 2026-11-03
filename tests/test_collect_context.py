"""Offline synthetic tests for the actual read-only HTTP evidence collector."""
import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from collect_context import (GitHubRead, LinearRead, ReadOnlyHTTP, collect,
                             read_private_key, validate_plan, write_private,
                             snippet)
from evidence_context import canonical, validate_evidence_packet


SHA = "a" * 40


def story():
    return {"source_issue_id": "HOM-1972", "review_scope": "PILOT_RC",
            "story_type": "non-behavioral",
            "title": "Synthetic supervised session", "payload": "operator Start"}


def policy():
    return {"review_scope": "PILOT_RC",
            "evidence_linear_workspace": "sashafelix-homelab",
            "evidence_allowed_repositories": ["The-Dev-Spot/homelab"],
            "risk_register_status": "DRAFT", "adopted": False}


def plan():
    return {"schema_version": 1, "target_issue": "HOM-1972",
            "linear": [
                {"id": "HOM-1972", "scope": "PILOT_RC", "focus": "manual Start"},
                {"id": "HOM-1973", "scope": "TARGET_CAPACITY", "focus": "four"}
            ], "github": [
                {"repository": "The-Dev-Spot/homelab",
                 "ref": "main", "path": "stacks/clarity-pilot/README.md",
                 "scope": "PILOT_RC", "kind": "DOCUMENT", "focus": "isolated"}
            ]}


class FakeLinear:
    def __init__(self):
        self.calls = []
        self.change_on_second_read = False

    def issue(self, issue_id):
        self.calls.append(issue_id)
        doc = ("manual Start for one job and no implicit approval."
               if issue_id == "HOM-1972" else
               "four worker slots in two pools, provider quota separate.")
        updated = "2026-11-03T08:00:00Z"
        if self.change_on_second_read and self.calls.count(issue_id) > 1:
            updated = "2026-11-03T08:00:01Z"
        return {"identifier": issue_id, "title": "Synthetic",
                "description": doc, "updatedAt": updated}


class FakeGitHub:
    def __init__(self):
        self.calls = []
        self.move_branch = False

    def commit(self, repo, ref):
        self.calls.append(("commit", repo, ref))
        if self.move_branch and len([c for c in self.calls if c[0] == "commit"]) > 1:
            return "b" * 40
        return SHA

    def file(self, repo, path, sha):
        self.calls.append(("file", repo, path, sha))
        return "# Documentation\n\nThis isolated pilot is not an autonomous PR workflow.\n"


class FakeHTTP:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def json(self, method, url, headers, data=None):
        self.calls.append((method, url, headers, data))
        return self.payload


class CollectorTests(unittest.TestCase):
    def test_collect_pins_revisions_and_rechecks_current_sources(self):
        linear, github = FakeLinear(), FakeGitHub()
        result = collect(plan(), story(), policy(), linear, github)
        self.assertEqual(len(result["sources"]), 3)
        self.assertEqual(result["freshness"], "SOURCE_UNVERIFIED")
        self.assertEqual(linear.calls, ["HOM-1972", "HOM-1973",
                                        "HOM-1972", "HOM-1973"])
        self.assertEqual(len([x for x in github.calls if x[0] == "commit"]), 2)
        gh = result["sources"][2]
        self.assertEqual(gh["authority_claim"], "UNVERIFIED")
        self.assertIn("/blob/" + SHA + "/stacks/clarity-pilot/README.md#L", gh["url"])
        self.assertEqual(validate_evidence_packet(result, story(), policy()), result)

    def test_changed_linear_issue_or_moved_github_branch_is_not_current(self):
        linear, github = FakeLinear(), FakeGitHub()
        linear.change_on_second_read = True
        self.assertEqual(collect(plan(), story(), policy(), linear, github)["freshness"],
                         "SOURCE_CHANGED")
        github = FakeGitHub()
        github.move_branch = True
        self.assertEqual(collect(plan(), story(), policy(), FakeLinear(), github)["freshness"],
                         "SOURCE_CHANGED")

    def test_unlisted_repository_or_traversal_never_reaches_network(self):
        selector = plan()
        selector["github"][0]["repository"] = "someone/else"
        with self.assertRaisesRegex(ValueError, "authorized"):
            validate_plan(selector, story(), policy())
        selector = plan()
        selector["github"][0]["path"] = "../../.ssh/id_rsa"
        with self.assertRaisesRegex(ValueError, "path"):
            validate_plan(selector, story(), policy())
        selector = plan()
        selector["github"][0]["ref"] = "feature/bad"
        with self.assertRaisesRegex(ValueError, "authorized"):
            validate_plan(selector, story(), policy())
        selector = plan()
        selector["linear"].append({"id": "HOM-1972", "scope": "PILOT_RC", "focus": ""})
        with self.assertRaisesRegex(ValueError, "repeated"):
            validate_plan(selector, story(), policy())

    def test_reject_missing_target_or_wrong_scope(self):
        selection = plan()
        selection["target_issue"] = "HOM-9999"
        with self.assertRaisesRegex(ValueError, "canonical story"):
            validate_plan(selection, story(), policy())
        selection = plan()
        selection["linear"][0]["scope"] = "PILOT-@"
        with self.assertRaisesRegex(ValueError, "selection"):
            validate_plan(selection, story(), policy())

    def test_no_implicit_file_discovery_or_malicious_focus(self):
        self.assertRaisesRegex(ValueError, "focus", snippet,
                               "authorized current decision", "nonexistent")
        gh=FakeGitHub()
        collect(plan(), story(), policy(), FakeLinear(), gh)
        self.assertEqual([x for x in gh.calls if x[0]=="file"],
                         [("file", "The-Dev-Spot/homelab",
                           "stacks/clarity-pilot/README.md", SHA)])

    def test_graphql_is_read_only_and_errors_are_blocking(self):
        payload = {"data": {"issue": {
            "identifier": "HOM-1972", "title": "Test",
            "description": "Manual", "updatedAt": "2026-11-03T08:00:00Z"}}}
        http = FakeHTTP(payload)
        result = LinearRead(http, "dummy-key").issue("HOM-1972")
        self.assertEqual(result["title"], "Test")
        self.assertEqual(http.calls[0][0], "POST")
        self.assertIn("query ClarityEvidenceIssue", http.calls[0][3]["query"])
        self.assertNotIn("mutation", http.calls[0][3]["query"].lower())
        partial = FakeHTTP(dict(payload, errors=[{"message":"forbidden"}]))
        with self.assertRaisesRegex(ValueError, "partial"):
            LinearRead(partial, "dummy-key").issue("HOM-1972")

    def test_commit_and_pinned_file_decode_and_missing_content_fail_closed(self):
        http = FakeHTTP({"sha": SHA})
        github = GitHubRead(http, "dummy-key")
        self.assertEqual(github.commit("The-Dev-Spot/homelab", "main"), SHA)
        self.assertIn("/commits/main", http.calls[0][1])
        encoded = base64.b64encode(b"the intended code").decode()
        http = FakeHTTP({"type":"file", "encoding":"base64",
                         "content":encoded, "size":17})
        self.assertEqual(GitHubRead(http, "dummy-key").file(
            "The-Dev-Spot/homelab", "README.md", SHA), "the intended code")
        self.assertIn("ref=" + SHA, http.calls[0][1])
        http = FakeHTTP({"type":"dir", "content":encoded, "size":17})
        with self.assertRaisesRegex(ValueError, "bounded text"):
            GitHubRead(http, "dummy-key").file("The-Dev-Spot/homelab","README.md",SHA)

    def test_transport_allows_only_fixed_hosts_and_read_operations(self):
        http=ReadOnlyHTTP()
        for method, url in (
            ("POST", "https://evil.example/graphql"),
            ("GET", "http://api.github.com/repos/a/b"),
            ("DELETE", "https://api.github.com/repos/a/b"),
            ("POST", "https://api.github.com/repos/a/b"),
            ("GET", "https://api.linear.app/graphql")
        ):
            with self.assertRaises(ValueError):
                http.json(method, url, {})

    def test_credential_shaped_source_text_is_blocked_before_model_use(self):
        with self.assertRaisesRegex(ValueError,"Possible credential"):
            snippet("User sent ghp_" + "A"*32, "")
        with self.assertRaisesRegex(ValueError,"Possible credential"):
            snippet("Authorization: Bearer " + "a"*45, "")
        self.assertIn("credential", snippet("The policy forbids sharing credentials.", ""))

    def test_current_canonical_document_is_read_and_revision_pinned(self):
        doc_id = "75bd04a6-f34d-478e-81c8-3ec27b7f66e4"
        doc_url = ("https://linear.app/sashafelix-homelab/document/"
                   "forge-city-canonical-decision-and-scope-register-v1-2026-11-01-f97f7d002a4d")
        selection=plan()
        selection["documents"] = [{
            "id": doc_id, "url": doc_url, "scope": "PILOT_RC",
            "focus": "PILOT_RC"
        }]

        class Documents(FakeLinear):
            def __init__(self):
                super().__init__()
                self.document_calls=0

            def document(self, value):
                self.document_calls+=1
                return {"id": value, "url":doc_url,
                        "title":"Canonical decisions",
                        "content":"PILOT_RC manually started; TARGET_AUTO future service",
                        "updatedAt":"2026-11-03T08:10:00Z"}

        linear=Documents()
        packet=collect(selection,story(),policy(),linear,FakeGitHub())
        self.assertEqual(linear.document_calls, 2)
        self.assertEqual(packet["sources"][2]["source_kind"], "DOCUMENT")
        self.assertEqual(packet["sources"][2]["url"],doc_url)
        self.assertEqual(packet["sources"][2]["authority_claim"],"UNVERIFIED")
        self.assertEqual(validate_evidence_packet(packet,story(),policy()),packet)

        selection["documents"][0]["url"] = "https://evil.example/steal"
        with self.assertRaisesRegex(ValueError,"document selection"):
            validate_plan(selection,story(),policy())

    def test_linear_document_graphql_partial_or_mismatched_id_is_rejected(self):
        docid="75bd04a6-f34d-478e-81c8-3ec27b7f66e4"
        obj={"id":docid,"title":"Documentation","content":"Plan",
             "updatedAt":"2026-11-03T08:10:00Z",
             "url":"https://linear.app/sashafelix-homelab/document/example-abc"}
        http=FakeHTTP({"data":{"document":obj}})
        document=LinearRead(http,"fake-key").document(docid)
        self.assertEqual(document["title"],"Documentation")
        self.assertIn("query ClarityEvidenceDocument",http.calls[0][3]["query"])
        self.assertNotIn("mutation",http.calls[0][3]["query"].lower())
        http=FakeHTTP({"data":{"document":dict(obj,id="someone-else")}})
        with self.assertRaisesRegex(ValueError,"incomplete"):
            LinearRead(http,"fake-key").document(docid)
        http=FakeHTTP({"data":{"document":obj},
                       "errors":[{"message":"permission denied"}]})
        with self.assertRaisesRegex(ValueError,"partial"):
            LinearRead(http,"fake-key").document(docid)

    def test_private_key_file_mode_symlinks_and_output_exclusive(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)
            p.chmod(0o700)
            key=p/"linear.key"
            key.write_text("test-key-string-long-enough-12345")
            key.chmod(0o600)
            self.assertTrue(read_private_key(key).startswith("test-key"))
            key.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "owner-only"):
                read_private_key(key)
            key.chmod(0o600)
            alias=p/"alias"
            alias.symlink_to(key)
            with self.assertRaisesRegex(ValueError, "private file"):
                read_private_key(alias)
            output=p/"evidence.json"
            record=collect(plan(), story(), policy(), FakeLinear(), FakeGitHub())
            write_private(output, record)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertIn("clarity-context-evidence", output.read_text())
            with self.assertRaises(FileExistsError):
                write_private(output, record)

    def test_policy_freshness_and_authority_remain_unverified(self):
        record=collect(plan(),story(),policy(),FakeLinear(),FakeGitHub())
        for entry in record["sources"][:2]:
            self.assertEqual(entry["authority_claim"], "UNVERIFIED")
        self.assertNotIn("ACCEPTED_FOR_FORGE", canonical(record))
        self.assertNotIn("CURRENT_VERIFIED", canonical(record))


if __name__=="__main__":
    unittest.main()
