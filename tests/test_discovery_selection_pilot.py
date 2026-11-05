"""Selection -> real collector contracts -> offline replay, with synthetic APIs."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from discover_github_research import discover
from evidence_context import canonical, digest
from preview_github_review import prepare
from question_relevance_research import build_prompt, research
from run_offline_pilot import main as pilot_main, replay
from select_discovery_evidence import (
    compile_selection, load_collection, main as selection_main, read_snapshot, recollect, write_collection,
)
from test_recheck_github_sources import FakeFreshGitHub
import test_reconcile_question_evidence as fixtures

DOC = "stacks/clarity-context-collector/README.md"


class Sources(FakeFreshGitHub):
    def tree(self, repo, sha):
        return [{"path": DOC, "type": "blob", "mode": "100644"}]

    def pull_numbers(self, repo, term):
        return []


class SelectionPilotTests(unittest.TestCase):
    def setUp(self):
        self.flow = fixtures.ReconciliationTests()
        self.flow.setUp()
        self.s, self.p, self.key = self.flow.f.s, self.flow.f.p, self.flow.key
        repo = self.s["source_issue_id"].split("#")[0]
        plan = {"schema_version": 1, "target_issue": self.s["source_issue_id"], "review_scope": self.s["review_scope"],
                "repository": repo, "document_prefixes": ["stacks/clarity-context-collector"], "terms": ["GitHub-only"]}
        self.discovery = discover(plan, self.s, self.p, Sources())
        self.selection = {"schema_version": 1, "kind": "clarity-discovery-document-selection",
                          "target_issue": self.s["source_issue_id"],
                          "discovery_sha256": digest(canonical(self.discovery).encode()), "candidate_ids": ["D-001"]}
        self.values = recollect(self.discovery, self.selection, self.s, self.p, Sources(), self.key)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.collection = self.root / "collection"
        write_collection(self.collection, self.values, self.s, self.p)

    def rebind_reports(self):
        flow, f = self.flow, self.flow.f
        old = f.prev
        decisions = copy.deepcopy(flow.r["proposals"]["decisions"])
        f.e = self.values["evidence.json"]
        f.hashes = f.hashes[:2] + (digest((canonical(f.e) + "\n").encode()),)
        f.report["evidence_file_sha256"] = f.hashes[2]
        f.prev = prepare(self.s, self.p, f.e, report=f.report, story_file_sha=f.hashes[0],
                         policy_file_sha=f.hashes[1], evidence_file_sha=f.hashes[2])
        by_question = {t["question"]: t["topic_id"] for t in f.prev["question_topics"]}
        ids = {t["topic_id"]: by_question[t["question"]] for t in old["question_topics"]}
        for decision in decisions:
            decision["topic_id"] = ids[decision["topic_id"]]
            if decision["duplicate_of"]:
                decision["duplicate_of"] = ids[decision["duplicate_of"]]
        for a in f.assessments:
            a["topic_id"] = ids[a["topic_id"]]
        prompt, _ = build_prompt(f.prev, f.e, None, count=3)
        receipt = dict(flow.r["receipt"], prompt_sha256=digest(prompt.encode()))
        with patch("question_relevance_research.run_claude_research", return_value=(decisions, receipt)):
            flow.r = research(self.s, self.p, f.e, f.report, f.prev, f.hashes, count=3, provider="claude")
        flow.make_challenge()
        # Evidence and signed original discussion match the fixture; serialization alone changed.
        self.assertEqual(flow.readback["evidence_sha256"], digest(canonical(f.e).encode()))
        flow.sign()
        return {"review": f.report, "research": flow.r, "challenge": flow.c, "freshness": flow.fresh}

    def test_selection_produces_real_v3_evidence_and_private_completed_bundle(self):
        values, hashes = load_collection(self.collection, self.s, self.p, self.key)
        self.assertEqual(values["evidence.json"]["schema_version"], 3)
        self.assertEqual(values["collection-plan.json"]["files"][0]["path"], DOC)
        self.assertEqual(len(hashes), 5)
        self.assertEqual(self.collection.stat().st_mode & 0o777, 0o700)
        for path in self.collection.iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(self.key.decode(), path.read_text())

    def test_evidence_only_replay_marks_models_not_run_not_zero_questions(self):
        with patch("subprocess.run", side_effect=AssertionError("No model/process")), \
                patch("collect_context.ReadOnlyHTTP.json", side_effect=AssertionError("No network")):
            out = replay(self.s, self.p, self.flow.f.hashes[:2], self.collection, self.key)
        self.assertEqual(out["status"], "BLOCKED")
        self.assertIsNone(out["topic_count"])
        self.assertIsNone(out["topics"])
        for stage in ("review", "research", "challenge", "freshness"):
            self.assertEqual(out["stages"][stage], "NOT_RUN")
        self.assertFalse(out["approval_authority"])
        self.assertFalse(out["forge_dispatch_authority"])

    def test_full_offline_replay_preserves_every_topic_and_authority_block(self):
        reports = self.rebind_reports()
        with patch("subprocess.run", side_effect=AssertionError("No model/process")), \
                patch("collect_context.ReadOnlyHTTP.json", side_effect=AssertionError("No network")):
            out = replay(self.s, self.p, self.flow.f.hashes[:2], self.collection, self.key, reports, now=1000)
        self.assertEqual(out["status"], "BLOCKED")
        self.assertEqual(out["topic_count"], 3)
        self.assertEqual(len(out["unresolved_topic_ids"]), 3)
        self.assertEqual(out["stages"]["freshness"], "AUTHENTICATED_MATCH_AT_READ_TIME")
        self.assertFalse(out["reconciliation"]["approval_authority"])

    def test_partial_prefix_replays_do_not_invent_later_stages(self):
        reports = self.rebind_reports()
        for names in (("review",), ("review", "research"), ("review", "research", "challenge")):
            with self.subTest(names=names):
                subset = {k: reports[k] for k in names}
                out = replay(self.s, self.p, self.flow.f.hashes[:2], self.collection, self.key, subset)
                self.assertEqual(out["topic_count"], 3)
                self.assertEqual(out["stages"]["freshness"], "NOT_RUN")

    def test_missing_stages_null_reports_and_expired_receipts_fail(self):
        for reports in ({"research": {}}, {"review": {}, "challenge": {}}, {"review": None}, []):
            with self.subTest(reports=reports), self.assertRaises(ValueError):
                replay(self.s, self.p, self.flow.f.hashes[:2], self.collection, self.key, reports)
        reports = self.rebind_reports()
        with self.assertRaisesRegex(ValueError, "expired"):
            replay(self.s, self.p, self.flow.f.hashes[:2], self.collection, self.key, reports, now=1291)

    def test_modified_source_review_and_challenge_fail_during_replay(self):
        reports = self.rebind_reports()
        for stage in ("review", "research", "challenge"):
            changed = copy.deepcopy(reports)
            changed[stage]["target_issue"] = "another/repository#1"
            if stage == "review":
                changed[stage]["evidence_file_sha256"] = "0" * 64
            with self.subTest(stage=stage), self.assertRaises(ValueError):
                replay(self.s, self.p, self.flow.f.hashes[:2], self.collection, self.key, changed, now=1000)

    def test_selection_is_explicit_unique_and_bound_to_exact_discovery(self):
        for mutate in (lambda s: s.update(candidate_ids=[]), lambda s: s.update(candidate_ids=["D-001", "D-001"]),
                       lambda s: s.update(candidate_ids=["D-999"]), lambda s: s.update(discovery_sha256="0" * 64),
                       lambda s: s.update(target_issue="HIST-101")):
            selected = copy.deepcopy(self.selection)
            mutate(selected)
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                compile_selection(self.discovery, selected, self.s, self.p)

    def test_selected_pr_is_refused_without_becoming_intake(self):
        discovery = copy.deepcopy(self.discovery)
        discovery["candidates"][0]["source_kind"] = "PULL_REQUEST"
        selected = dict(self.selection, discovery_sha256=digest(canonical(discovery).encode()))
        with self.assertRaisesRegex(ValueError, "PR adapter"):
            compile_selection(discovery, selected, self.s, self.p)

    def test_forged_authority_scope_url_and_paths_fail_before_network(self):
        for mutate in (lambda d: d.update(approval_authority=True),
                       lambda d: d.update(documents_scanned=0),
                       lambda d: d.update(repository="another/repo"),
                       lambda d: d["candidates"][0].update(path="../secrets.md"),
                       lambda d: d["candidates"][0].update(path="outside/file.md"),
                       lambda d: d["candidates"][0].update(url="https://evil.invalid/source"),
                       lambda d: d["candidates"][0].update(revision="main")):
            discovery = copy.deepcopy(self.discovery)
            mutate(discovery)
            selected = dict(self.selection, discovery_sha256=digest(canonical(discovery).encode()))
            github = Sources()
            with self.subTest(discovery=discovery), self.assertRaises(ValueError):
                recollect(discovery, selected, self.s, self.p, github, self.key)
            self.assertEqual(github.calls, [])

    def test_stale_discovery_and_changed_pinned_content_fail(self):
        discovery = copy.deepcopy(self.discovery)
        discovery["head_sha"] = "e" * 40
        discovery["candidates"][0]["revision"] = "e" * 40
        discovery["candidates"][0]["url"] = discovery["candidates"][0]["url"].replace("a" * 40, "e" * 40)
        selected = dict(self.selection, discovery_sha256=digest(canonical(discovery).encode()))
        with self.assertRaisesRegex(ValueError, "stale"):
            recollect(discovery, selected, self.s, self.p, Sources(), self.key)
        discovery = copy.deepcopy(self.discovery)
        discovery["candidates"][0]["content_sha256"] = "0" * 64
        selected = dict(self.selection, discovery_sha256=digest(canonical(discovery).encode()))
        with self.assertRaisesRegex(ValueError, "pinned content"):
            recollect(discovery, selected, self.s, self.p, Sources(), self.key)

    def test_tampered_bundle_completion_marker_and_unsafe_files_fail(self):
        evidence = self.collection / "evidence.json"
        evidence.write_text(evidence.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "completion receipt"):
            load_collection(self.collection, self.s, self.p, self.key)
        receipt = self.collection / "collection-receipt.json"
        receipt.unlink()
        with self.assertRaises(OSError):
            load_collection(self.collection, self.s, self.p, self.key)

    def test_private_reader_refuses_symlinks_public_files_and_duplicate_fields(self):
        path = self.root / "input.json"
        path.write_text('{"duplicate":1,"duplicate":2}')
        path.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            read_snapshot(path)
        path.write_text("{}")
        path.chmod(0o644)
        with self.assertRaises(ValueError):
            read_snapshot(path)
        link = self.root / "link.json"
        link.symlink_to(path)
        with self.assertRaises(OSError):
            read_snapshot(link)
        fifo = self.root / "fifo.json"
        os.mkfifo(fifo, mode=0o600)
        with self.assertRaises(ValueError):
            read_snapshot(fifo)

    def test_wrong_snapshot_key_and_reused_output_directory_fail(self):
        with self.assertRaisesRegex(ValueError, "authentication"):
            load_collection(self.collection, self.s, self.p, b"a-different-synthetic-key-long-enough")
        with self.assertRaises(FileExistsError):
            write_collection(self.collection, self.values, self.s, self.p)

    def test_pilot_cli_uses_no_network_or_model_and_writes_private_report(self):
        argv = ["pilot", "--collection-dir", str(self.collection)]
        for name, value in (("story", self.s), ("policy", self.p)):
            path = self.root / (name + ".json")
            path.write_text(json.dumps(value, sort_keys=True))
            path.chmod(0o600)
            argv += ["--" + name, str(path)]
        key = self.root / "collector.key"
        key.write_bytes(self.key)
        key.chmod(0o600)
        output = self.root / "pilot.json"
        argv += ["--collector-key-file", str(key), "--output", str(output)]
        with patch("sys.argv", argv), patch("subprocess.run", side_effect=AssertionError("No process/model")), \
                patch("collect_context.ReadOnlyHTTP.json", side_effect=AssertionError("No network")):
            self.assertEqual(pilot_main(), 0)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(output.read_text())["stages"]["review"], "NOT_RUN")

    def test_invalid_selection_cli_refuses_before_credentials_or_output(self):
        argv = ["select"]
        for name, value in (("discovery", self.discovery), ("selection", dict(self.selection, candidate_ids=[])),
                            ("story", self.s), ("policy", self.p)):
            path = self.root / (name + ".json")
            path.write_text(json.dumps(value))
            path.chmod(0o600)
            argv += ["--" + name, str(path)]
        output = self.root / "invalid"
        argv += ["--github-key-file", str(self.root / "none.key"), "--collector-key-file", str(self.root / "none2.key"),
                 "--output-dir", str(output)]
        with patch("sys.argv", argv), patch("select_discovery_evidence.read_private_key") as reader:
            self.assertEqual(selection_main(), 3)
        reader.assert_not_called()
        self.assertFalse(output.exists())

    def test_selection_cli_collects_bundle_and_full_pilot_cli_replays_it(self):
        argv = ["selection"]
        for name, value in (("discovery", self.discovery), ("selection", self.selection), ("story", self.s), ("policy", self.p)):
            path = self.root / (name + ".json")
            path.write_text(json.dumps(value, sort_keys=True))
            path.chmod(0o600)
            argv += ["--" + name, str(path)]
        key, github_key = self.root / "collector.key", self.root / "github.key"
        key.write_bytes(self.key)
        github_key.write_text("synthetic-github-read-token-only")
        key.chmod(0o600)
        github_key.chmod(0o600)
        folder = self.root / "cli-collection"
        argv += ["--collector-key-file", str(key), "--github-key-file", str(github_key), "--output-dir", str(folder)]
        with patch("sys.argv", argv), patch("select_discovery_evidence.GitHubResearchClient", return_value=Sources()):
            self.assertEqual(selection_main(), 0)
        reports = self.rebind_reports()
        pilot = ["pilot", "--story", str(self.root / "story.json"), "--policy", str(self.root / "policy.json"),
                 "--collector-key-file", str(key), "--collection-dir", str(folder), "--output", str(self.root / "full-pilot.json")]
        for name, value in reports.items():
            path = self.root / (name + ".json")
            path.write_text(json.dumps(value))
            path.chmod(0o600)
            pilot += ["--" + name, str(path)]
        with patch("sys.argv", pilot), patch("question_freshness_attestation.time.time", return_value=1000), \
                patch("subprocess.run", side_effect=AssertionError("No model/process")), \
                patch("collect_context.ReadOnlyHTTP.json", side_effect=AssertionError("No network")):
            self.assertEqual(pilot_main(), 0)
        report = json.loads((self.root / "full-pilot.json").read_text())
        self.assertEqual(report["topic_count"], 3)
        self.assertEqual(report["status"], "BLOCKED")

    def test_incomplete_collection_write_has_no_completion_marker(self):
        from select_discovery_evidence import write_private
        def fail(path, data):
            if path.name == "discussion-snapshot.json":
                raise OSError("Synthetic storage failure")
            return write_private(path, data)
        folder = self.root / "partial"
        with patch("select_discovery_evidence.write_private", side_effect=fail):
            with self.assertRaises(OSError):
                write_collection(folder, self.values, self.s, self.p)
        self.assertFalse((folder / "collection-receipt.json").exists())
        with self.assertRaises(OSError):
            load_collection(folder, self.s, self.p, self.key)

    def test_linear_history_is_context_and_changes_invalidate_existing_research(self):
        history = self.flow.f.case.history()
        out = replay(self.s, self.p, self.flow.f.hashes[:2], self.collection, self.key, history=history)
        self.assertEqual(out["linear_history_authority"], "HISTORICAL_UNVERIFIED")
        reports = self.rebind_reports()
        with self.assertRaisesRegex(ValueError, "exact prompt"):
            replay(self.s, self.p, self.flow.f.hashes[:2], self.collection, self.key, reports, history=history, now=1000)


if __name__ == "__main__":
    unittest.main()
