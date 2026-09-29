import copy
import json
import tempfile
import unittest
from pathlib import Path

from clarity.guardrails import Approval, ValidationError, authorize_plan, digest, identifier, load_config, load_json, open_questions, readiness

ROOT = Path(__file__).resolve().parents[1]


def complete_report():
    return {"dimensions": {f"D{i}": "PASS" for i in range(1, 11)}, "checks": {f"L{i}": "PASS" for i in range(1, 9)}, "open_questions": [], "unconfirmed_proposals": [], "interface_touched": False, "regulated": False, "injection_detected": False}


class ReadinessTests(unittest.TestCase):
    def test_complete_pass(self):
        self.assertEqual(readiness(complete_report())["verdict"], "READY")

    def test_each_hard_dimension_blocks(self):
        for name in ("D1", "D2", "D3", "D4", "D5", "D6"):
            with self.subTest(name=name):
                report = complete_report(); report["dimensions"][name] = "FAIL"
                self.assertEqual(readiness(report)["gate"], "FAIL")

    def test_each_hard_lint_blocks(self):
        for name in ("L1", "L2", "L3", "L5", "L7"):
            with self.subTest(name=name):
                report = complete_report(); report["checks"][name] = "FAIL"
                self.assertEqual(readiness(report)["gate"], "FAIL")

    def test_soft_failure_is_warning_not_pass(self):
        report = complete_report(); report["dimensions"]["D7"] = "FAIL"
        self.assertEqual(readiness(report)["gate"], "WARN")

    def test_interface_escalation(self):
        report = complete_report(); report["dimensions"]["D9"] = "FAIL"; report["interface_touched"] = True
        self.assertEqual(readiness(report)["gate"], "FAIL")

    def test_regulated_escalation(self):
        report = complete_report(); report["dimensions"]["D10"] = "FAIL"; report["regulated"] = True
        self.assertEqual(readiness(report)["gate"], "FAIL")

    def test_any_warning_blocks_ready(self):
        report = complete_report(); report["checks"]["L8"] = "WARN"
        self.assertEqual(readiness(report)["verdict"], "NOT READY")

    def test_missing_dimension_rejected(self):
        report = complete_report(); del report["dimensions"]["D6"]
        with self.assertRaises(ValidationError): readiness(report)

    def test_missing_check_rejected(self):
        report = complete_report(); del report["checks"]["L1"]
        with self.assertRaises(ValidationError): readiness(report)

    def test_not_run_cannot_clear_gate(self):
        report = complete_report(); report["checks"]["L1"] = "NOT_RUN"
        result = readiness(report)
        self.assertTrue(result["incomplete"])
        self.assertEqual(result["verdict"], "NOT READY")

    def test_questions_and_proposals_block(self):
        for field in ("open_questions", "unconfirmed_proposals"):
            report = complete_report(); report[field] = ["Requires owner confirmation"]
            self.assertEqual(readiness(report)["verdict"], "NOT READY")

    def test_injection_blocks(self):
        report = complete_report(); report["injection_detected"] = True
        self.assertEqual(readiness(report)["gate"], "FAIL")

    def test_string_boolean_rejected(self):
        report = complete_report(); report["regulated"] = "false"
        with self.assertRaises(ValidationError): readiness(report)

    def test_unknown_status_rejected(self):
        report = complete_report(); report["dimensions"]["D1"] = "looks good"
        with self.assertRaises(ValidationError): readiness(report)

    def test_unknown_report_field_rejected(self):
        report = complete_report(); report["force_ready"] = True
        with self.assertRaises(ValidationError): readiness(report)


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.report = complete_report()
        self.plan = {"run_id": "RUN-demo", "mode": "review", "target": "DEMO-1", "source_revision": "revision-1", "report_digest": digest(self.report), "actions": ["update_description"], "payload": {"description": "Reviewed example"}}
        self.allowed = frozenset({"update_description", "post_comment", "publish_evidence", "update_acceptance_criteria", "create_issue"})

    def approval(self, **changes):
        values = dict(approval_id="APPROVAL-demo", run_id="RUN-demo", actor="human-reviewer", plan_digest=digest(self.plan), actions=frozenset(self.plan["actions"]), issued_at=100, expires_at=200)
        values.update(changes)
        return Approval(**values)

    def authorize(self, approval, **changes):
        options = dict(current_revision="revision-1", now=150, allowed_actions=self.allowed)
        options.update(changes)
        return authorize_plan(self.plan, self.report, approval, **options)

    def test_exact_approval_allowed_by_explicit_policy(self):
        self.assertEqual(self.authorize(self.approval()), ("update_description",))

    def test_no_approval(self):
        with self.assertRaises(ValidationError): self.authorize(None)

    def test_default_policy_denies_everything(self):
        with self.assertRaises(ValidationError): self.authorize(self.approval(), allowed_actions=frozenset())

    def test_changed_source(self):
        with self.assertRaises(ValidationError): self.authorize(self.approval(), current_revision="revision-2")

    def test_changed_payload(self):
        approval = self.approval(); self.plan["payload"]["description"] = "Changed after approval"
        with self.assertRaises(ValidationError): self.authorize(approval)

    def test_changed_target(self):
        approval = self.approval(); self.plan["target"] = "DEMO-2"
        with self.assertRaises(ValidationError): self.authorize(approval)

    def test_expired_future_overlong_and_nonfinite(self):
        for changes in ({"expires_at": 149}, {"issued_at": 151}, {"expires_at": 1200}, {"expires_at": float("nan")}, {"issued_at": True}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError): self.authorize(self.approval(**changes))

    def test_consumed_approval(self):
        with self.assertRaises(ValidationError): self.authorize(self.approval(), consumed_approvals=frozenset({"APPROVAL-demo"}))

    def test_wrong_actor_or_run(self):
        for changes in ({"actor": ""}, {"run_id": "RUN-other"}):
            with self.assertRaises(ValidationError): self.authorize(self.approval(**changes))

    def test_added_field_write_requires_new_approval(self):
        approval = self.approval(); self.plan["actions"].append("update_acceptance_criteria")
        with self.assertRaises(ValidationError): self.authorize(approval)

    def test_not_ready_description_blocked(self):
        self.report["open_questions"] = ["Which outcome?"]; self.plan["report_digest"] = digest(self.report)
        with self.assertRaises(ValidationError): self.authorize(self.approval())

    def test_not_ready_questions_comment_can_be_approved(self):
        self.report["open_questions"] = ["Which outcome?"]; self.plan["report_digest"] = digest(self.report)
        self.plan["actions"] = ["post_comment"]; self.plan["payload"] = {"comment": "Which outcome?"}
        self.assertEqual(self.authorize(self.approval()), ("post_comment",))

    def test_changed_report_invalidates_plan(self):
        approval = self.approval(); self.report["regulated"] = True
        with self.assertRaises(ValidationError): self.authorize(approval)

    def test_quarantine_blocks_even_comment(self):
        self.report["injection_detected"] = True; self.plan["report_digest"] = digest(self.report)
        self.plan["actions"] = ["post_comment"]
        with self.assertRaises(ValidationError): self.authorize(self.approval())

    def test_intake_cannot_edit_existing_issue(self):
        self.plan["mode"] = "intake"
        with self.assertRaises(ValidationError): self.authorize(self.approval())

    def test_review_cannot_create_issue(self):
        self.plan["actions"] = ["create_issue"]
        with self.assertRaises(ValidationError): self.authorize(self.approval())

    def test_intake_ready_creation_plan(self):
        self.plan["mode"] = "intake"; self.plan["actions"] = ["create_issue"]
        self.assertEqual(self.authorize(self.approval()), ("create_issue",))

    def test_duplicate_or_unknown_actions(self):
        for actions in (["post_comment", "post_comment"], ["delete_issue"], []):
            self.plan["actions"] = actions
            with self.assertRaises(ValidationError): self.authorize(self.approval())


class InputTests(unittest.TestCase):
    def test_question_union_not_maximum(self):
        a = "# OPEN QUESTION -> PO: Question A?\n"
        b = "# OPEN QUESTION -> PO: Question B?\n"
        self.assertEqual(len(open_questions(a, b)), 2)
        self.assertEqual(len(open_questions(a, a)), 1)

    def test_question_whitespace_deduplicates(self):
        self.assertEqual(len(open_questions("# OPEN QUESTION -> PO: Which  outcome?", "# OPEN QUESTION -> PO: which outcome?")), 1)

    def test_malformed_question_blocks(self):
        with self.assertRaises(ValidationError): open_questions("# OPEN QUESTION: missing owner")

    def test_path_traversal_rejected(self):
        for value in ("../secret", "/tmp/id", "a/b", "a\\b", "", "a" * 101):
            with self.assertRaises(ValidationError): identifier(value)

    def test_default_config_valid(self):
        self.assertFalse(load_config(ROOT / ".github/project-config.json")["integration"]["writes_enabled"])

    def test_config_mutations_fail_closed(self):
        original = load_config(ROOT / ".github/project-config.json")
        for section, key, value in (("integration", "writes_enabled", True), ("integration", "writes_enabled", "false"), ("integration", "base_url", "http://example.com"), ("integration", "base_url", "https://" + "user:pass@example.com"), ("limits", "rewrite_iterations", True), ("limits", "rewrite_iterations", 4), ("logbook", "inline_sections", ["../secret"]), ("logbook", "inline_sections", ["rewrite"])):
            cfg = copy.deepcopy(original); cfg[section][key] = value
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "config.json"; path.write_text(json.dumps(cfg))
                with self.assertRaises(ValidationError): load_config(path)

    def test_missing_configuration_has_no_fallback(self):
        with self.assertRaises(ValidationError): load_config(ROOT / "does-not-exist.json")

    def test_duplicate_json_and_nonfinite_rejected(self):
        for body in ('{"x": 1, "x": 2}', '{"x": NaN}'):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "input.json"; path.write_text(body)
                with self.assertRaises(ValidationError): load_json(path)

    def test_digest_is_order_independent(self):
        self.assertEqual(digest({"a": 1, "b": 2}), digest({"b": 2, "a": 1}))


if __name__ == "__main__":
    unittest.main()
