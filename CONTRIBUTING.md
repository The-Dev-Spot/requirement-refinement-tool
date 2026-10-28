# Contributing

This repository is the assistant-operated Jira/Confluence toolkit. Preserve its
agent, skill, mode, stage and approval behavior when changing neutral guidance.
The standalone application is maintained in https://github.com/The-Dev-Spot/clarity-end-goal.

Keep examples fictional. Never commit live identifiers, private connections, run
records, source documents, screenshots or credentials. Review the staged diff and
privately scan for identifiers specific to your organization before submitting.

Update affected agent instructions, skills, rubric and templates together. The
lean payload and complete evidence separation must remain coherent end to end.
Record unavailable tooling as NOT_RUN; do not claim a model judgment is deterministic.

## Maintainer verification

The optional validation dependencies live under `.github/validation/` and are
not required to use the assistant workflow. With Node.js 24+:

```sh
cd .github/validation
npm ci --ignore-scripts
node check-toolkit.mjs
```

Checks cover links/contracts, the fictional Gherkin/checklist examples, AC and size
budgets, approval/state regressions and private-artifact hygiene. They do not prove
semantic quality or certify a specific assistant/MCP installation.
