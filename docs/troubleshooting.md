# Troubleshooting

Run `clarity doctor --state /absolute/private/state` for dependency, permission,
SQLite and quality-resource checks. It makes no network calls and prints no secrets.

| Symptom | What to do |
| --- | --- |
| `clarity` command is missing | Activate the virtual environment and run `python -m pip install --no-deps .`. Use the absolute executable path in an MCP client. |
| No login-key files | Run `clarity setup`. Read the file locations printed by setup; paste a file's contents into Workspace login key. |
| Cross-origin changes are not allowed | Open the exact `http://127.0.0.1:8765` address printed at launch. Refresh sign-in after upgrading. Use the same host for the full session. |
| State must be owner-only | Use a private directory with mode 0700 and files with mode 0600, owned by the current POSIX user. Avoid symlinked paths. |
| Role cannot perform an action | Sign out and use the correct author, reviewer or operator key. Do not give the operator key to a model. |
| Source or policy changed | Refresh and regenerate the task/draft. A stale version or context cannot be submitted. |
| Model call input budget exceeded | Use smaller relevant source excerpts. This preflight rejection does not spend an inference attempt. |
| Model connection or schema failure | Verify server port, model ID, JSON-schema support and output budget. Run the synthetic check. Inspect the job before explicitly retrying. |
| Pending owner decisions | Answer or explicitly resolve them as operator. Another model call cannot supply authority. |
| Call or rewrite budget exhausted | Inspect prior results; an operator can authorize a new cycle with a reason. |
| Saved connection has no credential after restore | Re-enter its service token. Backups exclude all credentials. |
| Source import rejected | Verify team/project/space scope, object ID, credential permissions, source size and service availability. Capture a smaller verified excerpt if needed. |
| Model job is interrupted | Review current state and explicitly start a new job. No automatic resume is performed. |
| Native Windows permissions fail | Run the Python application inside WSL. Native Windows ACL support is not implemented. |

If reporting a failure, include command/version, OS, failing step and sanitized error
text. Exclude login keys, service credentials, private source text and raw model packets.
