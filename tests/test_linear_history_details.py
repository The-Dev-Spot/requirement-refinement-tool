"""Bounded historical Linear status/comment collection and downstream replay."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from collect_linear_history import collect_history, main, validate_plan
from evidence_context import canonical, digest
from linear_history_details import (
    DETAIL_QUERY, SCOPE_QUERY, LinearHistoryRead, history_source_index,
)
from question_relevance_gate import prepare_gate, validate_history
from question_relevance_research import build_prompt, research
from question_relevance_verify import validate_assessments
import test_reconcile_question_evidence as replay_fixtures


TEAM = "11111111-1111-1111-1111-111111111111"
PROJECT = "22222222-2222-2222-2222-222222222222"
ISSUE = "33333333-3333-3333-3333-333333333333"
STATE = "44444444-4444-4444-4444-444444444444"
COMMENT = "55555555-5555-5555-5555-555555555555"
USER = "66666666-6666-6666-6666-666666666666"
TIME = "2026-10-01T10:00:00Z"
QUOTE = "prior decision: manually approve deployments."


def selection(story, policy):
    return {"schema_version": 2, "target_issue": story["source_issue_id"],
            "review_scope": story["review_scope"], "workspace": "example-workspace",
            "allowed_issue_prefixes": ["HIST"],
            "historical_issues": [{"id": "HIST-101", "scope": story["review_scope"],
                                    "focus": "prior decision", "team_id": TEAM, "project_id": PROJECT}]}


def issue():
    return {"id": ISSUE, "identifier": "HIST-101",
            "url": "https://linear.app/example-workspace/issue/HIST-101/earlier-decision",
            "title": "Previous architecture", "description": None, "updatedAt": TIME,
            "team": {"id": TEAM, "key": "HIST"}, "project": {"id": PROJECT},
            "state": {"id": STATE, "name": "Done", "type": "completed"},
            "comments": {"nodes": [{"id": COMMENT, "issueId": ISSUE, "parentId": None,
                                     "url": "https://linear.app/example-workspace/issue/HIST-101/earlier-decision#comment-" + COMMENT,
                                     "body": QUOTE, "createdAt": TIME, "updatedAt": TIME,
                                     "user": {"id": USER}}],
                         "pageInfo": {"hasNextPage": False, "hasPreviousPage": False}}}


class FakeDetails:
    def __init__(self, item=None, mutate_second=None):
        self.item = copy.deepcopy(item or issue())
        self.calls = []
        self.mutate_second = mutate_second

    def history_issue(self, iid, **kwargs):
        self.calls.append(iid)
        result = copy.deepcopy(self.item)
        if self.mutate_second and len(self.calls) > 1:
            self.mutate_second(result)
        return result


class FakeHTTP:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def json(self, *args):
        self.calls.append(args)
        return self.response.pop(0) if isinstance(self.response, list) else self.response


class LinearHistoryDetailsTests(unittest.TestCase):
    def setUp(self):
        self.s = {"source_issue_id": "example-org/project#123", "review_scope": "APP_REVIEW"}
        self.p = {"review_scope": "APP_REVIEW", "evidence_allowed_repositories": ["example-org/project"]}
        self.plan = selection(self.s, self.p)

    def collect(self, fake=None):
        return collect_history(self.plan, self.s, self.p, fake or FakeDetails())

    def test_collects_current_historical_status_and_individually_citable_comments(self):
        fake = FakeDetails()
        packet = self.collect(fake)
        self.assertEqual(fake.calls, ["HIST-101", "HIST-101"])
        self.assertEqual(packet["schema_version"], 2)
        index = validate_history(packet, self.s, self.p)
        self.assertEqual(set(index), {"L-001", "L-C-" + COMMENT})
        self.assertEqual(index["L-C-" + COMMENT]["excerpt"], QUOTE)
        self.assertEqual(index["L-C-" + COMMENT]["parent_source_id"], "L-001")
        source = packet["historical_sources"][0]
        self.assertNotIn(QUOTE, source["excerpt"])
        self.assertEqual(source["history_context"]["state"]["type"], "completed")
        self.assertEqual(source["project_mapping"], "API_IDS_MATCH_OPERATOR_SELECTION")
        for key in ("approval_authority", "issue_intake_authority", "forge_dispatch_authority", "current_policy_authority"):
            self.assertIs(packet[key], False)

    def test_query_is_fixed_read_only_bounded_and_does_not_request_contact_data(self):
        http = FakeHTTP({"data": {"issue": issue()}})
        result = LinearHistoryRead(http, "synthetic-token-only").history_issue(
            "HIST-101", selection=self.plan["historical_issues"][0], workspace=self.plan["workspace"])
        self.assertEqual(result["identifier"], "HIST-101")
        method, url, headers, payload = http.calls[1]
        self.assertEqual(http.calls[0][3]["query"], SCOPE_QUERY)
        self.assertEqual((method, url), ("POST", "https://api.linear.app/graphql"))
        self.assertEqual(payload, {"query": DETAIL_QUERY, "variables": {"id": "HIST-101"}})
        self.assertIn("first: 21", DETAIL_QUERY)
        self.assertIn("includeArchived: true", DETAIL_QUERY)
        for forbidden in ("mutation", "email", "displayName", "issueUpdate"):
            self.assertNotIn(forbidden, DETAIL_QUERY)

    def test_partial_graphql_errors_and_missing_issue_fail_closed(self):
        for response in ({"errors": [{"message": "denied"}], "data": {"issue": issue()}},
                         {"data": {"issue": None}}, {"data": None}, {}):
            with self.subTest(response=response), self.assertRaises(ValueError):
                LinearHistoryRead(FakeHTTP(response), "synthetic-token-only").history_issue(
                    "HIST-101", selection=self.plan["historical_issues"][0], workspace=self.plan["workspace"])

    def test_scope_preflight_refuses_before_requesting_comment_content(self):
        wrong = issue()
        wrong["project"]["id"] = TEAM
        http = FakeHTTP({"data": {"issue": wrong}})
        with self.assertRaisesRegex(ValueError, "team/project"):
            LinearHistoryRead(http, "synthetic-token-only").history_issue(
                "HIST-101", selection=self.plan["historical_issues"][0], workspace=self.plan["workspace"])
        self.assertEqual(len(http.calls), 1)
        self.assertEqual(http.calls[0][3]["query"], SCOPE_QUERY)
        self.assertNotIn("comments", SCOPE_QUERY)
        self.assertNotIn("description", SCOPE_QUERY)

    def test_provider_identity_change_after_scope_preflight_is_rejected(self):
        changed = issue()
        changed["id"] = PROJECT
        http = FakeHTTP([{"data": {"issue": issue()}}, {"data": {"issue": changed}}])
        with self.assertRaisesRegex(ValueError, "identity changed"):
            LinearHistoryRead(http, "synthetic-token-only").history_issue(
                "HIST-101", selection=self.plan["historical_issues"][0], workspace=self.plan["workspace"])

    def test_plan_requires_explicit_team_project_and_github_target(self):
        for mutate in (lambda p: p.update(target_issue="HIST-101"),
                       lambda p: p["historical_issues"][0].pop("team_id"),
                       lambda p: p["historical_issues"][0].update(team_id="HIST"),
                       lambda p: p["historical_issues"][0].update(project_id="project-name")):
            plan = copy.deepcopy(self.plan)
            mutate(plan)
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                validate_plan(plan, self.s, self.p)

    def test_workspace_team_project_and_comment_issue_identity_must_match(self):
        for mutate in (lambda x: x.update(url=x["url"].replace("example-workspace", "another-workspace")),
                       lambda x: x.update(identifier="HIST-102"),
                       lambda x: x["team"].update(id=PROJECT),
                       lambda x: x["team"].update(key="OTHER"),
                       lambda x: x["project"].update(id=TEAM),
                       lambda x: x.update(project=None),
                       lambda x: x["comments"]["nodes"][0].update(issueId=PROJECT),
                       lambda x: x["comments"]["nodes"][0].update(url="https://linear.app/another-workspace/issue/HIST-101#comment-" + COMMENT)):
            item = issue()
            mutate(item)
            with self.subTest(item=item), self.assertRaises(ValueError):
                self.collect(FakeDetails(item))

    def test_unassigned_project_requires_explicit_null_selection(self):
        self.plan["historical_issues"][0]["project_id"] = None
        item = issue()
        item["project"] = None
        packet = self.collect(FakeDetails(item))
        validate_history(packet, self.s, self.p)
        with self.assertRaises(ValueError):
            self.collect(FakeDetails())

    def test_partial_or_oversized_comment_connections_fail_without_pagination(self):
        for mutate in (lambda x: x["comments"]["pageInfo"].update(hasNextPage=True),
                       lambda x: x["comments"]["pageInfo"].update(hasPreviousPage=True),
                       lambda x: x["comments"]["pageInfo"].update(hasNextPage=0),
                       lambda x: x["comments"]["nodes"].extend(x["comments"]["nodes"] * 20),
                       lambda x: x["comments"].pop("pageInfo")):
            item = issue()
            mutate(item)
            fake = FakeDetails(item)
            with self.subTest(item=item), self.assertRaises(ValueError):
                self.collect(fake)
            self.assertEqual(len(fake.calls), 1)

    def test_status_and_comment_changes_detected_at_unchanged_issue_revision(self):
        for mutate in (lambda x: x["state"].update(name="Reopened", type="started"),
                       lambda x: x["comments"]["nodes"][0].update(body="The old decision is superseded."),
                       lambda x: x["comments"]["nodes"].clear(),
                       lambda x: x["comments"]["nodes"].append(dict(x["comments"]["nodes"][0], id=USER,
                           url=x["comments"]["nodes"][0]["url"].replace(COMMENT, USER))),
                       lambda x: x["comments"]["nodes"][0].update(user=None)):
            with self.subTest(mutation=mutate):
                packet = self.collect(FakeDetails(mutate_second=mutate))
                self.assertEqual(packet["status"], "SOURCE_CHANGED")
                with self.assertRaises(ValueError):
                    validate_history(packet, self.s, self.p)

    def test_duplicate_comments_missing_parents_cycles_and_bad_dates_fail(self):
        for mutate in (lambda x: x["comments"]["nodes"].append(x["comments"]["nodes"][0]),
                       lambda x: x["comments"]["nodes"][0].update(parentId=USER),
                       lambda x: x["comments"]["nodes"][0].update(parentId=COMMENT),
                       lambda x: x["comments"]["nodes"][0].update(updatedAt="2026-02-31T10:00:00Z"),
                       lambda x: x["comments"]["nodes"][0].pop("user"),
                       lambda x: x.pop("state")):
            item = issue()
            mutate(item)
            with self.subTest(item=item), self.assertRaises(ValueError):
                self.collect(FakeDetails(item))

    def test_replies_and_unknown_authors_are_preserved_without_owner_inference(self):
        item = issue()
        item["comments"]["nodes"].append(dict(item["comments"]["nodes"][0], id=USER,
                                              parentId=COMMENT, user=None, body="Reply: check the current policy.",
                                              url=item["comments"]["nodes"][0]["url"].replace(COMMENT, USER)))
        packet = self.collect(FakeDetails(item))
        validate_history(packet, self.s, self.p)
        comment = packet["historical_sources"][0]["history_context"]["comments"][1]
        self.assertEqual(comment["parent_id"], COMMENT)
        self.assertIsNone(comment["author_id"])

    def test_comment_focus_can_be_found_beyond_its_first_excerpt(self):
        item = issue()
        item["comments"]["nodes"][0]["body"] = "Earlier discussion. " * 100 + QUOTE + " More detail." * 100
        packet = self.collect(FakeDetails(item))
        comment = packet["historical_sources"][0]["history_context"]["comments"][0]
        self.assertIn(QUOTE, comment["excerpt"])
        self.assertLessEqual(len(comment["excerpt"]), 800)
        self.assertTrue(comment["excerpt_truncated"])

    def test_missing_focus_oversized_discussion_and_obvious_credentials_fail(self):
        for body in ("Unrelated discussion only.", QUOTE + " x" * 50_000,
                     QUOTE + " github_pat_" + "a" * 35):
            item = issue()
            item["comments"]["nodes"][0]["body"] = body
            with self.subTest(body_length=len(body)), self.assertRaises(ValueError):
                self.collect(FakeDetails(item))

    def test_gate_revalidates_context_and_the_exact_selected_plan(self):
        baseline = self.collect()
        for mutate in (lambda x: x["selection"]["historical_issues"][0].update(team_id=PROJECT),
                       lambda x: x["historical_sources"][0]["history_context"]["state"].update(type="APPROVED"),
                       lambda x: x["historical_sources"][0]["history_context"]["comments"][0].update(excerpt="Forged answer"),
                       lambda x: x["historical_sources"][0]["history_context"]["comments"][0].update(citation_id="L-001"),
                       lambda x: x.update(approval_authority=True),
                       lambda x: x["historical_sources"].clear()):
            packet = copy.deepcopy(baseline)
            mutate(packet)
            with self.subTest(packet=packet), self.assertRaises(ValueError):
                validate_history(packet, self.s, self.p)

    def test_duplicate_comment_identity_across_issues_is_rejected(self):
        packet = self.collect()
        second = copy.deepcopy(packet["historical_sources"][0])
        second.update(id="L-002", source_issue_id="HIST-102", url="https://linear.app/example-workspace/issue/HIST-102")
        packet["historical_sources"].append(second)
        with self.assertRaisesRegex(ValueError, "reused"):
            history_source_index(packet)

    def test_full_reconciliation_accepts_history_as_non_authoritative_context(self):
        flow = replay_fixtures.ReconciliationTests()
        flow.setUp()
        flow.history = collect_history(selection(flow.f.s, flow.f.p), flow.f.s, flow.f.p, FakeDetails())
        prompt, _ = build_prompt(flow.f.prev, flow.f.e, flow.history, count=3)
        self.assertIn("L-C-" + COMMENT, prompt)
        self.assertIn("Done", prompt)
        self.assertIn(digest(canonical(flow.history).encode()), prompt)
        receipt = dict(flow.r["receipt"], prompt_sha256=digest(prompt.encode()))
        decisions = copy.deepcopy(flow.r["proposals"]["decisions"])
        owner = next(d for d in decisions if d["topic_id"] == flow.f.approval_id)
        owner["evidence"] = [{"source_id": "L-C-" + COMMENT, "quote": QUOTE}]
        with patch("question_relevance_research.run_claude_research", return_value=(decisions, receipt)):
            flow.r = research(flow.f.s, flow.f.p, flow.f.e, flow.f.report, flow.f.prev,
                              flow.f.hashes, history=flow.history, count=3, provider="claude")
        flow.f.assessments[1]["source_quotes"] = [{"source_id": "L-C-" + COMMENT, "quote": QUOTE}]
        flow.make_challenge()
        flow.sign()
        out = flow.run_reconcile()
        self.assertEqual(out["status"], "BLOCKED")
        self.assertEqual(out["linear_history_authority"], "HISTORICAL_UNVERIFIED")
        self.assertFalse(out["approval_authority"])
        self.assertFalse(out["forge_dispatch_authority"])
        changed = issue()
        changed["state"].update(type="started", name="Reopened")
        flow.history = collect_history(selection(flow.f.s, flow.f.p), flow.f.s, flow.f.p, FakeDetails(changed))
        with self.assertRaisesRegex(ValueError, "exact prompt"):
            flow.run_reconcile()

    def test_history_comments_cannot_resolve_factual_github_answers(self):
        flow = replay_fixtures.ReconciliationTests()
        flow.setUp()
        history = collect_history(selection(flow.f.s, flow.f.p), flow.f.s, flow.f.p, FakeDetails())
        assessments = copy.deepcopy(flow.f.assessments)
        assessments[0]["source_quotes"] = [{"source_id": "L-C-" + COMMENT, "quote": QUOTE}]
        with self.assertRaisesRegex(ValueError, "independent GitHub citation"):
            validate_assessments(assessments, flow.r, flow.f.e, history)
        proposals = copy.deepcopy(flow.r["proposals"])
        fact = next(d for d in proposals["decisions"] if d["topic_id"] == flow.f.doc_id)
        fact["evidence"] = [{"source_id": "L-C-" + COMMENT, "quote": QUOTE}]
        with self.assertRaisesRegex(ValueError, "current GitHub"):
            prepare_gate(flow.f.s, flow.f.p, flow.f.e, flow.f.report, flow.f.prev,
                         flow.f.hashes, history=history, proposals=proposals)
        fact["evidence"][0]["source_id"] = "L-001"
        with self.assertRaisesRegex(ValueError, "quote not present"):
            prepare_gate(flow.f.s, flow.f.p, flow.f.e, flow.f.report, flow.f.prev,
                         flow.f.hashes, history=history, proposals=proposals)

    def test_cli_private_output_and_changed_source_refusal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            argv = ["linear-history"]
            for name, value in (("plan", self.plan), ("story", self.s), ("policy", self.p)):
                path = root / (name + ".json")
                path.write_text(json.dumps(value))
                argv += ["--" + name, str(path)]
            key = root / "linear.key"
            key.write_text("synthetic-history-token-never-live")
            key.chmod(0o600)
            output = root / "packet.json"
            argv += ["--linear-key-file", str(key), "--output", str(output)]
            with patch("sys.argv", argv), patch("collect_linear_history.LinearHistoryRead", return_value=FakeDetails()):
                self.assertEqual(main(), 0)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(key.read_text(), output.read_text())
            output.unlink()
            changed = FakeDetails(mutate_second=lambda x: x["comments"]["nodes"].clear())
            with patch("sys.argv", argv), patch("collect_linear_history.LinearHistoryRead", return_value=changed):
                self.assertEqual(main(), 3)
            self.assertFalse(output.exists())

    def test_invalid_selection_refuses_before_reading_the_token(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bad_plan = copy.deepcopy(self.plan)
            bad_plan["target_issue"] = "HIST-101"
            argv = ["linear-history"]
            for name, value in (("plan", bad_plan), ("story", self.s), ("policy", self.p)):
                path = root / (name + ".json")
                path.write_text(json.dumps(value))
                argv += ["--" + name, str(path)]
            argv += ["--linear-key-file", str(root / "no.key"), "--output", str(root / "no.json")]
            with patch("sys.argv", argv), patch("collect_linear_history.read_private_key") as token:
                self.assertEqual(main(), 3)
            token.assert_not_called()


if __name__ == "__main__":
    unittest.main()
