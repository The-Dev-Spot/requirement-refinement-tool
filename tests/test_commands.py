import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from clarity.__main__ import main
from clarity.benchmark import run
from clarity.guardrails import load_json
from clarity.runtime import Workflow

ROOT = Path(__file__).resolve().parents[1]


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def invoke(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = main(args)
        return code, output.getvalue()

    def test_init_and_provision_do_not_print_secret(self):
        args = ["work", "--state", str(self.root / "state")]
        self.assertEqual(self.invoke(args + ["init"])[0], 0)
        key = self.root / "author.key"
        code, output = self.invoke(args + ["provision", "writer", "author", "--output", str(key)])
        self.assertEqual(code, 0)
        self.assertNotIn(key.read_text().strip(), output)
        self.assertEqual(key.stat().st_mode & 0o777, 0o600)
        authenticated = args + ["--token-file", str(key)]
        code, _ = self.invoke(authenticated + ["create", "RUN-cli", str(ROOT / "examples/checklist-requirement.json")])
        self.assertEqual(code, 0)
        code, output = self.invoke(authenticated + ["status", "RUN-cli"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output)["run"]["state"], "awaiting_review")
        self.assertEqual(self.invoke(authenticated + ["verify", "RUN-cli"])[0], 0)
        self.assertEqual(self.invoke(authenticated + ["view", "RUN-cli", "--output", str(self.root / "review.html")])[0], 0)
        self.assertEqual(self.invoke(authenticated + ["view", "RUN-cli", "--output", str(self.root / "review.html")])[0], 2)

    def test_no_credential_reports_validation_error(self):
        code, output = self.invoke(["work", "--state", str(self.root / "state"), "list"])
        self.assertEqual(code, 2)
        self.assertNotIn("Traceback", output)

    def test_bad_json_does_not_dump_input(self):
        path = self.root / "bad.json"; path.write_text('{"secret":"do-not-echo",')
        code, output = self.invoke(["lint", str(path)])
        self.assertEqual(code, 2)
        self.assertNotIn("do-not-echo", output)

    def test_lint_cli(self):
        self.assertEqual(self.invoke(["lint", str(ROOT / "examples/checklist-requirement.json")])[0], 0)

    def test_fixture_benchmark(self):
        result = run(load_json(ROOT / "examples/rule-benchmark.json"))
        self.assertEqual(result["passed"], result["total"])
        self.assertEqual(result["total"], 13)
        self.assertFalse(result["semantic_accuracy_measured"])
        self.assertEqual(self.invoke(["benchmark", str(ROOT / "examples/rule-benchmark.json")])[0], 0)

    def test_benchmark_catches_wrong_expected_label(self):
        suite = load_json(ROOT / "examples/rule-benchmark.json")
        suite["cases"][0]["expected_flags"] = ["L1"]
        result = run(suite)
        self.assertEqual(result["passed"], result["total"] - 1)

    def test_no_overwrite_existing_workspace(self):
        args = ["work", "--state", str(self.root / "state"), "init"]
        self.assertEqual(self.invoke(args)[0], 0)
        self.assertEqual(self.invoke(args)[0], 2)


if __name__ == "__main__":
    unittest.main()
