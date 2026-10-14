# Workbench browser regression

These tests submit rendered login, capture, model setup, source-file and logout forms in Chromium, and check a narrow responsive viewport.
They also save stage limits, inspect the pre-run context budget, and run an optional
intake against a synthetic provider to verify that it never creates a draft.
They do not set Origin or other browser-generated request headers manually.
The fixture uses a disposable loopback workspace and synthetic keys; no model,
external tracker, real credentials or existing workspace is used.

Both CI workflows run on the self-hosted `host:r720-ai` Linux x64 runner.
Python 3.11/3.13 core jobs and Python 3.12 browser checks use disposable Debian
Bookworm Python containers, so interpreter/browser packages stay within the job.
The runner must be available to this repository and have Docker installed.

The separate browser CI job requires this suite to run, rather than silently
skipping it when a browser is absent. The lightweight core suite still runs with
only the runtime lock file.

On Ubuntu or Debian Bookworm x86_64 with CPython 3.12, from the repository root:

```sh
python -m pip install --require-hashes --only-binary=:all: -r requirements.lock -r requirements-browser.lock
python -m playwright install --with-deps --only-shell chromium
python -m unittest discover -s tests/browser -v
```

The browser dependency lock targets CPython 3.12 on glibc-based Linux x86_64. Runtime
requirements remain in requirements.lock; browser dependencies are development
tools, not additional application requirements.

Coverage includes browser-generated Origin on same-origin form submissions,
session rotation, capture, logout and no Referer on a link to a second loopback
origin. Null, missing and foreign Origin rejection and CSRF enforcement remain in
the HTTP suite.
