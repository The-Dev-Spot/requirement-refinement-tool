# Workbench browser regression

These tests submit rendered login, capture, model setup, source-file and logout forms in Chromium, and check a narrow responsive viewport.
They do not set Origin or other browser-generated request headers manually.
The fixture uses a disposable loopback workspace and synthetic keys; no model,
external tracker, real credentials or existing workspace is used.

The separate browser CI job requires this suite to run, rather than silently
skipping it when a browser is absent. The lightweight core suite still runs with
only the runtime lock file.

On Ubuntu x86_64 with CPython 3.12, from the repository root:

```sh
python -m pip install --require-hashes --only-binary=:all: -r requirements.lock -r requirements-browser.lock
python -m playwright install --with-deps --only-shell chromium
python -m unittest discover -s tests/browser -v
```

The browser dependency lock intentionally targets the platform above. Runtime
requirements remain in requirements.lock; browser dependencies are development
tools, not additional application requirements.

Coverage includes browser-generated Origin on same-origin form submissions,
session rotation, capture, logout and no Referer on a link to a second loopback
origin. Null, missing and foreign Origin rejection and CSRF enforcement remain in
the HTTP suite.
