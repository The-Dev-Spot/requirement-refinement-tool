# Xray edition pilot

Clarity exports the exact approved Gherkin. It does not create Jira/Xray records.
Choose Xray Cloud or Xray Server/Data Center and an authorized disposable test
project before testing its actual import route.

## Check the selected instance

1. Seal a handoff using the intended Xray export profile. Retain its manifest and
   the SHA-256 of `acceptance.feature`.
2. Configure the target project's required fields and explicit requirement links.
   Do not infer tracker keys from Clarity IDs or import private source evidence.
3. Import only the approved feature using the selected edition's documented route.
4. Check every stable `@case_ID`, Rule/Background, outline, example row, Data Table
   and Doc String against the approved text. Confirm Test counts and requirement links.
5. Record a one-to-one scenario → Test-key mapping. Repeat the same import and a
   changed-revision import. Observe creation/update behavior; never assume deduplication.
6. Record the chosen repeat strategy: update explicitly mapped Tests, or create an
   explicitly tracked new version. Check the remote records and retain the receipt.

Example receipt shape (replace values with observed evidence):

```json
{
  "edition": "xray-cloud",
  "project": "DEMO",
  "feature_sha256": "SHA256_OF_APPROVED_FEATURE",
  "scenario_tests": {"SC1": "DEMO-1"},
  "repeat_strategy": "update-mapped-tests",
  "observations": {
    "scenario_ids": "NOT_RUN",
    "outlines": "NOT_RUN",
    "backgrounds": "NOT_RUN",
    "tables_docstrings": "NOT_RUN",
    "requirement_links": "NOT_RUN",
    "repeat_import": "NOT_RUN"
  }
}
```

Use PASS, FAIL, NOT_RUN or NOT_APPLICABLE for each observation, with supporting
notes/evidence retained separately. Validate the local receipt:

```sh
python -m clarity.handoff_check /absolute/private/acceptance.feature /absolute/private/pilot-receipt.json
```

The checker validates the selected edition/project, approved hash, complete unique
scenario mapping and observation fields. It performs no network call and always
reports `remote_state_verified: false`. A complete receipt is operator-reported
evidence, not independent remote verification.

Feature files specify tests; executing them still requires real step definitions,
fixtures and a suitable environment. Consult the edition references in the
[handoff standard](handoff-standard.md).
