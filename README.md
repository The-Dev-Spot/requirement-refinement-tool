# Clarity

Turn a rough idea into a requirement people can build and test.

Clarity is a local application for capturing a need, selecting evidence, resolving
business decisions and producing a reviewed developer handoff. Use Copilot, Codex,
Claude Code or a locally hosted model. Every starting point meets the same final
quality standard. Gherkin is the canonical acceptance format.

## Start here

Requires Python 3.11+ on Linux, macOS or WSL with POSIX file permissions.
From this checkout:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes --only-binary=:all: -r requirements.lock
python -m pip install --require-hashes --only-binary=:all: -r requirements-build.lock
python -m pip install --no-deps --no-build-isolation .
clarity setup
clarity start
```

Open **http://127.0.0.1:8765**. Setup prints the locations of three private login
files: `author.key`, `reviewer.key` and `operator.key`. Paste a file's contents into
**Workspace login key** to use that role. Sign out to switch roles.

1. Sign in as **operator**, then open **Setup** to configure your assistant/local
   model, source connections and project quality settings.
2. Sign in as **author**. Capture the problem in plain language and attach relevant
   source versions. Connect your coding assistant or run a saved local model.
3. Use **operator** to answer consequential questions and confirm source applicability.
4. Use **reviewer** in a fresh assistant conversation to check the draft independently.
5. Use **operator** to inspect and approve the exact handoff, then seal and download it.

Model use is opt-in. No model is downloaded or selected automatically.
The workspace defaults to `~/.local/share/clarity`; use `--state /absolute/path`
with setup, start and doctor to choose another private location.

## Choose how to run

| Option | How it connects | What you need |
| --- | --- | --- |
| Copilot in VS Code | Scoped stdio MCP server | Your configured Copilot client |
| Codex | Scoped stdio MCP server | Your configured Codex client |
| Claude Code | Scoped stdio MCP server | Your configured Claude Code client |
| Ollama | `127.0.0.1:<port>/api/chat` | A running model with JSON-schema support |
| LM Studio, vLLM or a custom local server | OpenAI-compatible Chat Completions on loopback | JSON-schema support and the exact model ID |
| OpenAI or Anthropic API | Optional fixed HTTPS provider | An API key and explicit permission to send selected evidence |

Open a requirement's **Connect your assistant** panel for client configuration.
Assistant login stays in that client; subscriptions are not reused as API keys.
The bridge exposes task retrieval, result submission and on-demand diagnostics for one requirement.
It cannot answer owner questions, configure policy, approve or publish.
See [assistant setup](docs/assistants.md) and [model setup](docs/models.md).

## Sources and handoffs

Capture text or UTF-8 files in **Sources**, or explicitly read a selected Linear
issue, Jira Cloud issue or Confluence Cloud page. Connections enforce the selected
team, project or space. Captured versions retain their source locator, revision,
effective date when known and retrieval time. An operator confirms applicability.
Attach only the relevant excerpts; changes require a fresh draft and review.

The normal download contains **requirement.md** and the unchanged **acceptance.feature**.
The full sealed audit bundle retains coverage, citations, selected evidence,
independent review and a hash manifest; download it separately when needed. Approval binds
that exact revision and expires after 15 minutes. Unresolved questions, unsupported
claims and objective quality failures block delivery.

Import only **acceptance.feature** into test management. The full audit ZIP contains
selected evidence. Cucumber, Xray Cloud and Xray Server/DC profiles are local export choices;
no tracker write or verified live import is implied. See [the Xray pilot](docs/xray-pilot.md).

Optional [project collaboration tools](docs/project-collaboration.md) add approved,
versioned glossaries, focused stakeholder questionnaires and a portable view of an
already sealed handoff. These are local CLI operations; no development pipeline is
required or automatically started.

## Guides

- [First run and daily use](docs/refinement-workflow.md)
- [Assistant connections](docs/assistants.md) and [local/cloud model setup](docs/models.md)
- [Efficient model use, smaller handoffs and usage measurements](docs/efficiency.md)
- [Project glossaries, stakeholder questionnaires and portable handoffs](docs/project-collaboration.md)
- [Source management](docs/sources.md), [backup and recovery](docs/recovery.md), [troubleshooting](docs/troubleshooting.md)
- [Handoff standard](docs/handoff-standard.md), [operating contract](AGENTS.md), [security](SECURITY.md)
- [Quality evaluation](docs/evaluation.md), [architecture](docs/architecture.md), [remaining qualification](docs/roadmap.md)
- [Prepare a clean recipient handover](docs/data-hygiene.md) and [upgrade checklist](docs/upgrade-notes.md)
- [Specialist role library](.github/agents/README.md) and [contributing](CONTRIBUTING.md)

## Development and verification

```sh
python -m unittest discover -s tests -v
python -m clarity validate-config
python -m clarity check-repo
python -m pip install --require-hashes --only-binary=:all: -r requirements-build.lock
python -m pip wheel --no-deps --no-build-isolation .
```

Stage new source files before the tracked-file hygiene scan. Browser checks have a
separate [setup guide](tests/browser/README.md). Use [evaluation](docs/evaluation.md)
to assess a chosen model; passing unit tests does not prove semantic correctness or
equal real-world outcomes across input styles.

This is one trusted local workspace. Keep the listener on loopback and keep private
state out of shared repositories. It is not a hosted multi-user identity system.
The older snapshot CLI remains for [compatibility](docs/standalone-workflow.md);
its exports do not satisfy the current Gherkin handoff contract.
