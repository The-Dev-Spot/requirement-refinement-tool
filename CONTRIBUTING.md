# Contributing

Read [AGENTS.md](AGENTS.md) for the quality and authority contract. Prefer small,
reviewable changes that improve the final requirement rather than its self-score.

Use Python 3.11+ on a POSIX system. Create a virtual environment, install the
hash-locked runtime requirements, then `python -m pip install --no-deps -e .`.

```sh
python -m unittest discover -s tests -v
python -m clarity validate-config
python -m clarity lint examples/checklist-requirement.json
python -m clarity benchmark examples/rule-benchmark.json
python -m clarity gate examples/complete-report.json
python -m clarity check-repo
python -m pip wheel --no-deps .
```

Stage new source files before the tracked-file scan. Check the resulting wheel
outside the checkout: setup, doctor and loopback startup must work without the
repository's documentation paths. Follow the separate browser-test instructions
for real-browser verification. Use the quality corpus for model/prompt changes;
fixtures cannot establish semantic quality.

Keep examples fictional and use reserved example domains. Do not commit keys,
private state, live source data, logs or local MCP client settings. Update relevant
guides and runtime contracts when behavior changes. Run meaningful regression tests
for authority, stale context, output validation and recovery boundaries.

No merge, public deployment, remote tracker write or automatic retention deletion
is part of a local implementation change. Record actual validation and any remaining
live-model/client qualification in the PR.

## CI runner

Core and browser CI target `[self-hosted, Linux, X64, host:r720-ai]` and use
disposable Python Bookworm containers. Core checks retain Python 3.11 and 3.13;
browser checks use Python 3.12. The runner needs Docker and repository access.
Jobs run for main-branch pushes and same-repository pull requests. Branch pushes
with an open PR do not duplicate the PR checks, and fork PRs do not execute on
the personal runner. No GitHub-hosted fallback consumes hosted Actions minutes.
