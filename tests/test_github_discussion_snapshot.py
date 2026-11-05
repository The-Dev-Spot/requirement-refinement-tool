"""Original discussion integrity: no credentials, external APIs, or models."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from collect_github_context import collect, collect_with_snapshot, issue_text, main as collect_main
from evidence_context import canonical, digest, validate_evidence_packet
from github_discussion_snapshot import capture_snapshot, validate_snapshot
from question_freshness_attestation import attest_freshness
from recheck_github_sources import recheck, main as recheck_main
from reconcile_question_evidence import validate_readback
from preview_github_review import prepare
from test_github_question_triage import bound_data, eligible_policy
from test_github_context import plan, story, policy
from test_recheck_github_sources import FakeFreshGitHub

KEY = b"fictional-unit-test-original-snapshot-secret"


class LongDiscussion(FakeFreshGitHub):
    """Uncited comments sit beyond the bounded excerpt, with stable issue time."""
    def __init__(self, *, change=None, during_read=False):
        super().__init__()
        self.change = change
        self.during_read = during_read

    def issue(self, repo, number):
        item = super().issue(repo, number)
        item["body"] += "\n" + "More existing background. " * 200
        if self.change == "added":
            item["comments"] = 2
        if self.change == "deleted":
            item["comments"] = 0
        if self.change == "state":
            item["state"] = "closed"
        return item

    def comments(self, repo, number, count):
        comments = super().comments(repo, number, count)
        change = self.change if not self.during_read or self.comments_seen > 1 else None
        if change == "edited":
            comments[0]["body"] = "The previous decision is superseded; pause rollout."
        if change == "added":
            comments.append(dict(comments[0], id=102, body="Do not proceed; policy changed."))
        if change == "deleted":
            return []
        if change == "author":
            comments[0]["author"] = "different-author"
        if change == "identity":
            comments[0]["id"] = 999
        if change == "comment_time":
            comments[0]["updated_at"] = "2026-11-05T10:00:00Z"
        return comments


class DiscussionSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.s, self.p = story(), policy()
        self.e, self.snapshot = collect_with_snapshot(plan(), self.s, self.p,
                                                     LongDiscussion(), KEY)

    def recheck(self, github=None):
        return recheck(self.s, self.p, self.e, github or LongDiscussion(),
                       discussion_snapshot=self.snapshot, collector_key=KEY)

    def test_authenticated_original_is_in_reviewed_evidence_not_raw_discussion(self):
        self.assertEqual(self.e["schema_version"], 3)
        validate_evidence_packet(self.e, self.s, self.p)
        original = validate_snapshot(self.snapshot, self.e, KEY)
        self.assertEqual(set(original), {"S-001"})
        self.assertEqual(self.e["discussion_snapshot_sha256"],
                         digest(canonical(self.snapshot["payload"]["discussions"]).encode()))
        serialized = canonical(self.snapshot)
        self.assertNotIn("collector must remain", serialized)
        self.assertNotIn(KEY.decode(), serialized)

    def test_matching_full_discussion_can_be_reconciled_but_grants_no_authority(self):
        result = self.recheck()
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(result["recheck_status"], "MATCHED_AT_READ_TIME")
        validate_readback(result, self.e, self.snapshot, KEY)
        self.assertEqual(len(result["rechecked_discussions"]), 1)
        self.assertFalse(result["approval_authority"])
        self.assertFalse(result["forge_dispatch_authority"])

    def test_uncited_edits_additions_deletions_and_metadata_changes_are_detected(self):
        self.assertNotIn("collector must remain", self.e["sources"][0]["excerpt"])
        for change in ("edited", "added", "deleted", "author", "identity", "comment_time", "state"):
            with self.subTest(change=change):
                result = self.recheck(LongDiscussion(change=change))
                self.assertEqual(result["recheck_status"], "SOURCE_CHANGED")
                source = result["rechecked_sources"][0]
                self.assertEqual(source["claimed_revision"], source["observed_revision"])
                self.assertTrue(source["content_matches"])
                self.assertEqual(result["rechecked_discussions"][0]["status"], "SOURCE_CHANGED")
                with self.assertRaises(ValueError):
                    validate_readback(result, self.e, self.snapshot, KEY)

    def test_old_excerpt_only_recheck_demonstrates_the_gap(self):
        legacy = collect(plan(), self.s, self.p, LongDiscussion())
        old = recheck(self.s, self.p, legacy, LongDiscussion(change="edited"))
        self.assertEqual(old["recheck_status"], "MATCHED_AT_READ_TIME")
        self.assertEqual(self.recheck(LongDiscussion(change="edited"))["recheck_status"],
                         "SOURCE_CHANGED")
        with self.assertRaises(ValueError):
            validate_readback(old, legacy, None, KEY)

    def test_comment_change_during_recheck_invalidates_overall_receipt(self):
        result = self.recheck(LongDiscussion(change="edited", during_read=True))
        self.assertEqual(result["rechecked_discussions"][0]["status"], "MATCHED")
        self.assertEqual(result["recheck_status"], "SOURCE_CHANGED")
        self.assertEqual(result["discussion_integrity_status"], "SOURCE_CHANGED")

    def test_comment_change_during_initial_collection_cannot_be_signed(self):
        with self.assertRaises(ValueError):
            collect_with_snapshot(plan(), self.s, self.p,
                                  LongDiscussion(change="edited", during_read=True), KEY)

    def test_partial_comment_selection_fails_before_network(self):
        selection = plan()
        selection["issues"][0]["include_comments"] = False
        github = LongDiscussion()
        with self.assertRaisesRegex(ValueError, "requires comments"):
            collect_with_snapshot(selection, self.s, self.p, github, KEY)
        self.assertEqual(github.calls, [])

    def test_wrong_key_and_tampered_original_snapshot_are_rejected_before_network(self):
        for mutation in (lambda x: x["payload"]["discussions"][0].update(discussion_sha256="0" * 64),
                         lambda x: x["payload"].update(target_issue="another/repo#169")):
            value = copy.deepcopy(self.snapshot)
            mutation(value)
            github = LongDiscussion()
            with self.assertRaisesRegex(ValueError, "authentication"):
                recheck(self.s, self.p, self.e, github, discussion_snapshot=value, collector_key=KEY)
            self.assertEqual(github.calls, [])
        with self.assertRaises(ValueError):
            validate_snapshot(self.snapshot, self.e, b"another-fake-key-with-enough-bytes")

    def test_snapshot_cannot_be_recollected_after_review_to_hide_new_comments(self):
        new_evidence, new_snapshot = collect_with_snapshot(plan(), self.s, self.p,
                                                          LongDiscussion(change="edited"), KEY)
        # Excerpts and issue timestamps are identical, but reviewed evidence must differ.
        self.assertEqual(self.e["sources"], new_evidence["sources"])
        self.assertNotEqual(digest(canonical(self.e).encode()), digest(canonical(new_evidence).encode()))
        with self.assertRaisesRegex(ValueError, "binding"):
            validate_snapshot(new_snapshot, self.e, KEY)

    def test_changed_discussion_requires_new_review_not_just_new_snapshot(self):
        policy_for_review = eligible_policy()
        old, _ = collect_with_snapshot(plan(), self.s, policy_for_review, LongDiscussion(), KEY)
        report, _ = bound_data(self.s, policy_for_review, old)
        current, _ = collect_with_snapshot(plan(), self.s, policy_for_review,
                                          LongDiscussion(change="edited"), KEY)
        _, current_hashes = bound_data(self.s, policy_for_review, current)
        with self.assertRaisesRegex(ValueError, "exact private inputs"):
            prepare(self.s, policy_for_review, current, report=report,
                    story_file_sha=current_hashes[0], policy_file_sha=current_hashes[1],
                    evidence_file_sha=current_hashes[2])

    def test_v3_requires_an_exact_snapshot_digest_and_github_only_target(self):
        for value in (True, "", "not-a-digest"):
            packet = dict(self.e, discussion_snapshot_sha256=value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_evidence_packet(packet, self.s, self.p)
        packet = dict(self.e, target_issue="HIST-101")
        with self.assertRaises(ValueError):
            validate_evidence_packet(packet, self.s, self.p)

    def test_missing_repeated_or_wrong_discussion_coverage_is_rejected(self):
        original = self.snapshot["payload"]["discussions"]
        for changed in ([], original + original,
                        [dict(original[0], source_id="S-999")],
                        [dict(original[0], discussion_sha256="not-a-hash")]):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                capture_snapshot(self.e, changed, KEY)

    def test_legacy_packets_cannot_be_retrofitted_with_an_original_snapshot(self):
        legacy = collect(plan(), self.s, self.p, LongDiscussion())
        with self.assertRaisesRegex(ValueError, "recollection"):
            recheck(self.s, self.p, legacy, LongDiscussion(),
                    discussion_snapshot=self.snapshot, collector_key=KEY)
        with self.assertRaises(ValueError):
            self.recheck_without_snapshot()

    def recheck_without_snapshot(self):
        return recheck(self.s, self.p, self.e, LongDiscussion())

    def test_snapshot_and_freshness_signatures_cannot_substitute_for_each_other(self):
        result = self.recheck()
        wrong = attest_freshness(result, "a" * 64, KEY, 100, 101)
        with self.assertRaisesRegex(ValueError, "authentication"):
            validate_snapshot(wrong, self.e, KEY)

    def test_canonical_digest_distinguishes_identical_rendered_text(self):
        class AmbiguousText(LongDiscussion):
            def __init__(self, body_contains_comment):
                super().__init__()
                self.body_contains_comment = body_contains_comment

            def issue(self, repo, number):
                item = super().issue(repo, number)
                if self.body_contains_comment:
                    item["body"] += ("\n\n[Comment 101 by example, updated 2026-11-03T10:00:00Z]\n"
                                     "The collector must remain read only.")
                    item["comments"] = 0
                return item

            def comments(self, repo, number, count):
                return [] if self.body_contains_comment else super().comments(repo, number, count)

        a = issue_text(AmbiguousText(False), plan()["issues"][0])
        b = issue_text(AmbiguousText(True), plan()["issues"][0])
        self.assertEqual(a[2], b[2])
        self.assertNotEqual(a[1], b[1])

    def test_recheck_coverage_cannot_drop_or_substitute_a_digest(self):
        for mutate in (lambda r: r["rechecked_discussions"].clear(),
                       lambda r: r["rechecked_discussions"][0].update(observed_sha256="b" * 64),
                       lambda r: r.update(original_discussion_receipt_sha256="c" * 64)):
            result = self.recheck()
            mutate(result)
            with self.assertRaises(ValueError):
                validate_readback(result, self.e, self.snapshot, KEY)

    def test_collection_cli_writes_private_evidence_and_authenticated_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            argv = ["collect"]
            for name, value in (("plan", plan()), ("story", self.s), ("policy", self.p)):
                path = root / (name + ".json")
                path.write_text(json.dumps(value))
                path.chmod(0o600)
                argv += ["--" + name, str(path)]
            for name, value in (("github-key-file", b"synthetic-github-read-token-only"),
                                ("attestation-key-file", KEY)):
                path = root / (name + ".key")
                path.write_bytes(value)
                path.chmod(0o600)
                argv += ["--" + name, str(path)]
            output, snapshot = root / "evidence.json", root / "snapshot.json"
            argv += ["--output", str(output), "--snapshot-output", str(snapshot)]
            with patch("sys.argv", argv), patch("collect_github_context.GitHubEvidenceClient",
                                                return_value=LongDiscussion()):
                self.assertEqual(collect_main(), 0)
            e, receipt = json.loads(output.read_text()), json.loads(snapshot.read_text())
            validate_snapshot(receipt, e, KEY)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(snapshot.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(KEY.decode(), output.read_text() + snapshot.read_text())

    def test_signed_recheck_without_snapshot_refuses_before_loading_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            argv = ["recheck"]
            for name, value in (("story", self.s), ("policy", self.p), ("github-evidence", self.e)):
                path = root / (name + ".json")
                path.write_text(json.dumps(value))
                argv += ["--" + name, str(path)]
            argv += ["--challenge", str(root / "unused.json"),
                     "--attestation-key-file", str(root / "unused.key"),
                     "--github-key-file", str(root / "github.key"), "--output", str(root / "output.json")]
            with patch("sys.argv", argv), patch("recheck_github_sources.read_private_key") as token:
                self.assertEqual(recheck_main(), 3)
            token.assert_not_called()
            self.assertFalse((root / "output.json").exists())


if __name__ == "__main__":
    unittest.main()
