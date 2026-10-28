# Clarity connection setup

## Open and choose an entry

Open the repository in your assistant. Copilot users can choose story-orchestrator,
story-intake or story-creator from the agent picker. With Codex or Claude Code,
ask the assistant to read AGENTS.md and the appropriate `.github/agents/*.agent.md`
entry profile explicitly. The stage and approval rules are the same in each host.
Native profile and tool discovery differ; these files do not configure a host for you.

No standalone application installation is required. Use your existing assistant
and its configured tools. Start with pasted story text or the fictional example
before connecting real data.

## Configure your project

Copy `.github/project-config.yaml` to the ignored `.github/project-config.local.yaml`.
Fill in only your own Jira URL, project/board/team scope, real AC field mapping,
knowledge spaces and evidence root. Keep tokens in the host's connection settings
or your private secret store, never project configuration or committed files.
Populate private reference material under `Reference/private/`, and add approved
risk/glossary definitions locally before relying on domain-specific judgments.

For a real tracker run, use [MCP setup](mcp.md) and verify read access first.
The example.invalid URLs and fictional DEMO keys are never live destinations.
Missing configuration stops the relevant remote stage. A local-only draft can
still be staged; do not invent successful reads, parser results or publication.

On first use, the entry agent copies the four empty runtime-register templates
from `docs/agent/templates/registers/` to `docs/agent/`. These runtime files and
all run folders are ignored. Never commit live stories, answers or evidence.

## Run

> Review DEMO-1234

> New requirement: let customers cancel a booking before it starts.

Use review mode by default. The assistant investigates, evaluates, rewrites when
needed, quality-gates and runs PO analysis before staging. It waits for explicit
story-specific approval before any Jira write. Connected log-book writes are
scoped to the configured evidence subtree; grounding/spec pages are read-only.

Keep host approval controls enabled for writes. Read-only tools may use your host's
normal read permissions. Autopilot, silence and a READY verdict are not approval.
Stage roles are responsibilities, not credential or OS sandboxes. If independent
review or an actual mechanical check is unavailable, record NOT_RUN and keep it staged.

See the [user guide](user-guide.md) for the exact review/apply/intake commands.
