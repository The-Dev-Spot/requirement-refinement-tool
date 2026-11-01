"""Guardrails for the *draft* Clarity acceptance interface (not approval tests).

This verifies the source schema/template are well-formed and keep authority out
of the proposal. A future trusted acceptance implementation must use an actual
JSON Schema 2020-12 validator and authenticate decisions in its own supervisor.
"""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AcceptanceContractDraftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema=json.loads((ROOT/"schemas/requirement-acceptance-proposal-v1.schema.json").read_text())
        cls.policy=json.loads((ROOT/"policy/requirement-acceptance.example.json").read_text())

    def test_schema_draft_version_and_no_extra_authorization_fields(self):
        s=self.schema
        self.assertEqual(s["$schema"],"https://json-schema.org/draft/2020-12/schema")
        self.assertFalse(s["additionalProperties"])
        self.assertEqual(s["properties"]["kind"]["const"],"clarity-requirement-acceptance-proposal")
        self.assertEqual(s["properties"]["result"]["enum"],["CANDIDATE","NEEDS_DECISION","BLOCKED"])
        self.assertNotIn("ACCEPTED",s["properties"]["result"]["enum"])
        for forbidden in ("approved","can_execute","tool_permissions","critical","workorder"):
            self.assertNotIn(forbidden,s["properties"])
        self.assertFalse(s["properties"]["source"]["additionalProperties"])
        self.assertFalse(s["properties"]["project_policy"]["additionalProperties"])

    def test_all_hash_fields_are_required_and_lowercase_hex(self):
        s=self.schema
        self.assertEqual(s["$defs"]["sha256"]["pattern"],"^[0-9a-f]{64}$")
        self.assertEqual(s["properties"]["handoff_sha256"]["$ref"],"#/$defs/sha256")
        self.assertEqual(s["properties"]["quality_report_sha256"]["$ref"],"#/$defs/sha256")
        self.assertIn("content_sha256",s["properties"]["source"]["required"])
        self.assertIn("sha256",s["properties"]["project_policy"]["required"])
        self.assertIsNotNone(re.fullmatch(s["$defs"]["sha256"]["pattern"],"a"*64))
        self.assertIsNone(re.fullmatch(s["$defs"]["sha256"]["pattern"],"A"*64))

    def test_require_stable_nonempty_criterion_ids(self):
        cs=self.schema["properties"]["criterion_ids"]
        self.assertGreaterEqual(cs["minItems"],1)
        self.assertLessEqual(cs["maxItems"],8)
        self.assertTrue(cs["uniqueItems"])
        self.assertIn("AC-",cs["items"]["pattern"])

    def test_example_policy_is_explicitly_unapproved_and_no_auto_accept(self):
        p=self.policy
        self.assertEqual(p["status"],"DRAFT")
        self.assertFalse(p["approval"]["do_r_and_risk_policy_ratified"])
        self.assertTrue(p["approval"]["principal_verification"]=="REQUIRED")
        self.assertFalse(p["auto_accept"]["enabled"])
        for grant in ("merge","deploy","secret_access","critical_lane","production_change"):
            self.assertIn(grant,p["auto_accept"]["never_grants"])

    def test_readme_requires_trusted_issuer_and_existing_zip_compatibility(self):
        d=(ROOT/"docs/requirement-acceptance-gate-draft.md").read_text()
        self.assertIn("Forge v2",d)
        self.assertIn("data",d)
        self.assertIn("separate",d.lower())
        self.assertIn("ratified",d)
        self.assertIn("HOM-1972",d)


if __name__=="__main__":
    unittest.main()
