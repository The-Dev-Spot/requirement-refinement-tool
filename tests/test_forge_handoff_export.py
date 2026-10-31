"""Contract fixtures for the Clarity -> Forge portable handoff v2 exporter."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from export_forge_handoff import package, _hash


def criteria(kind="non-behavioral"):
    if kind == "behavioral":
        records = [{"id": "AC-1", "kind": "behavior", "text": "Only one import job exists",
                    "verification": "Observe the backend event test oracle", "scenario_id": "AC-1"}]
    else:
        records = [{"id": "AC-1", "kind": "operational", "text": "Normal and critical pool capacity stays bounded",
                    "verification": "Inspect per-pool worker lease state during test", "scenario_id": None}]
    return json.dumps({"schema_version": 2, "story_type": kind, "criteria": records}).encode()


FEATURE = b"Feature: Import dedupe\n  @case_AC-1\n  Scenario: Duplicate delivery\n    Given an import event exists\n    When the event is delivered twice\n    Then exactly one job exists\n"


def export(kind="non-behavioral", **overrides):
    data = dict(requirement=b"# Fix repeat processing\n\nBackend-only work.\n",
                criteria=criteria(kind), feature=FEATURE if kind == "behavioral" else None,
                run_id="HOM-123", revision=1, source_system="linear", source_ref="HOM-123")
    data.update(overrides)
    return package(**data)


class ExportTests(unittest.TestCase):
    def test_nonbehavioral_has_no_fake_feature(self):
        a = export()
        with zipfile.ZipFile(io.BytesIO(a)) as z:
            self.assertEqual(set(z.namelist()), {"requirement.md", "criteria.json", "handoff.json"})
            meta = json.loads(z.read("handoff.json"))
            self.assertEqual(meta["criterion_ids"], ["AC-1"])
            self.assertEqual(meta["story_type"], "non-behavioral")
            self.assertEqual(meta["files"]["criteria.json"], _hash(z.read("criteria.json")))
            self.assertNotIn("execution_authority", meta)

    def test_behavioral_has_original_gherkin(self):
        with zipfile.ZipFile(io.BytesIO(export("behavioral"))) as z:
            self.assertEqual(z.read("acceptance.feature"), FEATURE)
            self.assertEqual(json.loads(z.read("handoff.json"))["criterion_ids"], ["AC-1"])

    def test_deterministic_bytes(self):
        self.assertEqual(export(), export())

    def test_duplicate_or_unaligned_criterion_rejected(self):
        doc = json.loads(criteria())
        doc["criteria"].append(doc["criteria"][0].copy())
        with self.assertRaises(ValueError): export(criteria=json.dumps(doc).encode())
        with self.assertRaises(ValueError): export("behavioral", feature=FEATURE.replace(b"@case_AC-1", b"@case_WRONG"))

    def test_invalid_types_and_permission_fields_rejected(self):
        doc = json.loads(criteria())
        doc["execution_authority"] = True
        with self.assertRaises(ValueError): export(criteria=json.dumps(doc).encode())
        doc = json.loads(criteria())
        doc["criteria"][0]["kind"] = "behavior"
        with self.assertRaises(ValueError): export(criteria=json.dumps(doc).encode())

    def test_larger_than_8_fails_and_revision_bool_fails(self):
        doc = json.loads(criteria())
        doc["criteria"] = [{**doc["criteria"][0], "id": f"AC-{i}"} for i in range(1,10)]
        with self.assertRaises(ValueError): export(criteria=json.dumps(doc).encode())
        with self.assertRaises(ValueError): export(revision=True)

    def test_cli_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "req.md").write_text("Reviewed requirement")
            (root / "criteria.json").write_bytes(criteria())
            output = root / "export.zip"
            command = [sys.executable,
                       str(Path(__file__).resolve().parents[1] / "scripts" / "export_forge_handoff.py"),
                       "--requirement", str(root / "req.md"), "--criteria", str(root / "criteria.json"),
                       "--story-id", "HOM-123", "--revision", "1", "--source-system", "linear",
                       "--source-ref", "HOM-123", "--output", str(output)]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)
            self.assertGreater(output.stat().st_size, 0)

    def test_cli_refuses_symlink_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "real.md").write_text("Requirement")
            (root / "link.md").symlink_to(root / "real.md")
            (root / "criteria.json").write_bytes(criteria())
            result = subprocess.run([sys.executable,
                str(Path(__file__).resolve().parents[1] / "scripts" / "export_forge_handoff.py"),
                "--requirement", str(root / "link.md"), "--criteria", str(root / "criteria.json"),
                "--story-id", "REQ1", "--revision", "1", "--source-system", "local",
                "--source-ref", "REQ1", "--output", str(root / "a.zip")],
                capture_output=True)
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
