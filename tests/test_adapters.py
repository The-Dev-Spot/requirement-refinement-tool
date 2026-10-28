import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from clarity.adapters import ISSUE_QUERY, LinearReader, _NoRedirect, import_markdown
from clarity.guardrails import ValidationError


def page(after=False):
    return {"data": {"issue": {"id": "issue-1", "identifier": "DEMO-1", "title": "Example", "description": "Synthetic body", "updatedAt": "2026-09-29T08:00:00Z", "url": "https://linear.app/example/issue/DEMO-1", "team": {"id": "team-1"}, "project": {"id": "project-1"}, "comments": {"nodes": [{"id": "comment-2" if after else "comment-1", "body": "Synthetic comment", "updatedAt": "2026-09-29T08:00:00Z"}], "pageInfo": {"hasNextPage": not after, "endCursor": None if after else "cursor-1"}}}}}


class AdapterTests(unittest.TestCase):
    def reader(self, transport, **kwargs):
        return LinearReader("synthetic-key", "team-1", transport=transport, **kwargs)

    def test_complete_paginated_read(self):
        calls = []
        def transport(variables):
            calls.append(variables); return page(bool(variables["after"]))
        result = self.reader(transport).read_issue("DEMO-1")
        self.assertEqual(len(result["source"]["comments"]), 2)
        self.assertTrue(result["complete"])
        self.assertEqual(calls[1]["after"], "cursor-1")
        self.assertNotIn("mutation", ISSUE_QUERY.lower())

    def test_team_and_project_scope(self):
        for field in ("team", "project"):
            body = page(); body["data"]["issue"][field]["id"] = "outside-scope"
            with self.assertRaises(ValidationError):
                self.reader(lambda _: body, project_id="project-1").read_issue("DEMO-1")

    def test_partial_graphql_errors_fail_closed(self):
        body = page(); body["errors"] = [{"message": "private error content"}]
        with self.assertRaises(ValidationError) as error: self.reader(lambda _: body).read_issue("DEMO-1")
        self.assertNotIn("private error", str(error.exception))

    def test_absent_issue(self):
        with self.assertRaises(ValidationError): self.reader(lambda _: {"data": {"issue": None}}).read_issue("DEMO-1")

    def test_comment_page_budget(self):
        with self.assertRaises(ValidationError): self.reader(lambda _: page(), max_pages=1).read_issue("DEMO-1")

    def test_combined_byte_budget(self):
        body = page(); body["data"]["issue"]["description"] = "x" * 3000
        with self.assertRaises(ValidationError): self.reader(lambda _: body, max_bytes=1000).read_issue("DEMO-1")

    def test_repeated_cursor_or_duplicate_comment(self):
        with self.assertRaises(ValidationError): self.reader(lambda _: page()).read_issue("DEMO-1")

    def test_revision_change_mid_read(self):
        def transport(variables):
            data = page(bool(variables["after"]))
            if variables["after"]: data["data"]["issue"]["updatedAt"] = "2026-09-29T08:01:00Z"
            return data
        with self.assertRaises(ValidationError): self.reader(transport).read_issue("DEMO-1")

    def test_redirects_never_forward_credentials(self):
        with self.assertRaises(ValidationError): _NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.com/")

    def test_malformed_cursor(self):
        data = page(); data["data"]["issue"]["comments"]["pageInfo"]["endCursor"] = None
        with self.assertRaises(ValidationError): self.reader(lambda _: data).read_issue("DEMO-1")

    def test_auth_header_injection_rejected(self):
        with self.assertRaises(ValidationError): LinearReader("secret\nHeader: bad", "team-1")

    def test_local_import_provenance_and_source_revision(self):
        with tempfile.TemporaryDirectory() as folder:
            source, ac = Path(folder)/"brief.md", Path(folder)/"ac.md"
            source.write_text("Provide a tested restore guide.")
            ac.write_text("- [ ] Guide exists | Verify: inspect the committed document")
            first = import_markdown(source, ac, project="DEMO", source_id="SOURCE-1", source_date="2026-09-29", kind="checklist")
            ac.write_text("- [ ] Guide is tested | Verify: retain the transcript")
            second = import_markdown(source, ac, project="DEMO", source_id="SOURCE-1", source_date="2026-09-29", kind="checklist")
            self.assertNotEqual(first["source"]["revision"], second["source"]["revision"])
            self.assertEqual(first["evidence"][0]["source_date"], "2026-09-29")

    def test_local_import_refuses_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/"brief.md"; source.write_text("brief")
            link = Path(folder)/"link.md"; link.symlink_to(source)
            with self.assertRaises(ValidationError): import_markdown(link, source, project="DEMO", source_id="SOURCE-1", source_date="2026-09-29", kind="checklist")


if __name__ == "__main__":
    unittest.main()
