import json
import tempfile
import unittest
from pathlib import Path

from clarity.__main__ import main
from clarity.guardrails import ValidationError
from clarity.logbook import build

ROOT = Path(__file__).resolve().parents[1]


class LogbookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, body in {"run-summary": "# Summary\nSynthetic demonstration\n", "quality-gates": "# Verdict\nNOT READY\n", "rewrite": "# OPEN QUESTION -> PO: Question A?\n", "proposed-comment": "# OPEN QUESTION -> PO: Question B?\n"}.items():
            (self.root / ("DEMO-1-" + name + ".md")).write_text(body, encoding="utf-8")

    def test_verbatim_sections_and_union(self):
        body, manifest = build("DEMO-1", self.root, ["run-summary", "rewrite"])
        self.assertIn((self.root / "DEMO-1-rewrite.md").read_text(), body)
        self.assertIn("artifacts: 2", body)
        self.assertFalse(manifest["published"])
        self.assertEqual(len(manifest["files"]), 4)

    def test_missing_section_is_error(self):
        with self.assertRaises(ValidationError): build("DEMO-1", self.root, ["run-summary", "investigation"])

    def test_no_phantom_upload_claim(self):
        body, _ = build("DEMO-1", self.root, ["run-summary"])
        self.assertIn("No attachments have been uploaded", body)

    def test_excludes_previous_generated_page(self):
        (self.root / "DEMO-1-logbook-page.built.md").write_text("Prior output")
        _, manifest = build("DEMO-1", self.root, ["run-summary"])
        self.assertEqual(len(manifest["files"]), 4)

    def test_missing_summary_rejected(self):
        with self.assertRaises(ValidationError): build("DEMO-1", self.root, ["rewrite"])

    def test_unsafe_identifier(self):
        with self.assertRaises(ValidationError): build("../demo", self.root, ["run-summary"])

    def test_symlink_evidence_rejected(self):
        target = self.root / "DEMO-1-investigation.md"
        try:
            target.symlink_to(self.root / "DEMO-1-rewrite.md")
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks not supported")
        with self.assertRaises(ValidationError): build("DEMO-1", self.root, ["run-summary"])

    def test_cli_creates_manifest_and_refuses_overwrite(self):
        args = ["logbook", "DEMO-1", "--run-dir", str(self.root), "--config", str(ROOT / ".github/project-config.json")]
        self.assertEqual(main(args), 0)
        manifest = json.loads((self.root / "DEMO-1-manifest.json").read_text())
        self.assertFalse(manifest["published"])
        self.assertEqual(main(args), 2)


if __name__ == "__main__":
    unittest.main()
