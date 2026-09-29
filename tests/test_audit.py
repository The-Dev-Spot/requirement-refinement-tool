import subprocess
import tempfile
import unittest
from pathlib import Path

from clarity.audit import check_repository, scan_text


class AuditTests(unittest.TestCase):
    def test_placeholder_host_allowed(self):
        self.assertFalse(scan_text("https://example.com/docs contact@example.com"))

    def test_unreviewed_host_flagged_without_echoing_secret(self):
        findings = scan_text("https://" + "internal.invalid/path")
        self.assertIn("unreviewed host or credential-bearing URL", findings)

    def test_credential_literal_flagged(self):
        self.assertIn("credential-like literal", scan_text("ghp_" + "x" * 36))

    def test_private_email_flagged(self):
        self.assertIn("non-example email", scan_text("person@" + "internal.invalid"))

    def test_binary_and_runtime_artifacts_flagged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".env").write_text("PLACEHOLDER=example")
            (root / "README.md").write_text("# Safe example")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            self.assertTrue(any(".env:" in line for line in check_repository(root)))


if __name__ == "__main__":
    unittest.main()
