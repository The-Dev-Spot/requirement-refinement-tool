import json
import re
import unittest
from pathlib import Path

from clarity.guardrails import load_json, readiness

ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_readme_links_exist(self):
        for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", (ROOT / "README.md").read_text()):
            if not link.startswith("https://"):
                self.assertTrue((ROOT / link).exists(), link)

    def test_ten_scoped_agent_profiles(self):
        agents = list((ROOT / ".github/agents").glob("*.agent.md"))
        self.assertEqual(len(agents), 10)
        for path in agents:
            text = path.read_text()
            self.assertTrue(text.startswith("---\n"), path.name)
            frontmatter = text.split("---", 2)[1]
            self.assertIn("description:", frontmatter)
            tools = json.loads(re.search(r"^tools: (.+)$", frontmatter, re.M).group(1))
            self.assertTrue(set(tools) <= {"read", "search", "edit", "agent"})
            self.assertIn("AGENTS.md", text)

    def test_synthetic_fixture_and_runtime_contract(self):
        self.assertEqual(readiness(load_json(ROOT / "examples/complete-report.json"))["verdict"], "READY")
        contract = load_json(ROOT / ".github/agents/runtime-doc-contract.json")
        self.assertTrue(contract["implemented_workflow_engine"])
        self.assertFalse(contract["development_pipeline_integration"])
        self.assertFalse(contract["model_orchestration_implemented"])
        self.assertFalse(contract["approval"]["live_publisher_implemented"])


if __name__ == "__main__":
    unittest.main()
