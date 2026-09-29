# Contributing

Keep changes scoped, evidence-backed and reviewable. Preserve the cold-read test,
intake/review parity, explicit approval and the distinction between fact,
inference and proposal. Do not replace a failed check with a weaker prompt.

Before proposing a change:

```sh
python -m clarity validate-config
python -m unittest discover -s tests -v
git add <reviewed-files>
python -m clarity check-repo
```

The hygiene command scans tracked working-tree files; stage new files first.
Inspect the staged diff as well. Add negative tests for every policy change.
Never use private source material as fixtures. Document capabilities accurately:
planned features must not be presented as implemented or end-to-end tested.

Governance, rubric, approval, CI and learning-policy changes need explicit human
review. Branch protection and CODEOWNERS enforcement must be configured by an
administrator; their presence must not be assumed. Do not add an open-source
licence or change repository visibility without the owner's explicit decision.
