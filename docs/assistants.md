# Copilot, Codex and Claude Code

Use an installed, authenticated assistant that supports stdio MCP. Clarity does
not start a shell, launch a coding agent, collect its subscription token or convert
its subscription into HTTP model access. The same task packet can also be downloaded
and its result imported through the requirement page.

## Connect one requirement

1. Install Clarity and capture a requirement as author.
2. Open **Connect your assistant** on that requirement. It shows client-specific
   configuration using the current workspace path, requirement ID and role.
3. Replace `clarity` with the absolute path to your installed executable when your
   client does not inherit the virtual environment. Replace the key path if yours
   differs from the default `STATE/keys/author.key`.
4. Enable the MCP server in your assistant. Ask it to call `clarity_get_task`,
   investigate the supplied context and submit the exact contract through
   `clarity_submit_result`.

Example VS Code Copilot `.vscode/mcp.json`:

```json
{
  "servers": {
    "clarity": {
      "type": "stdio",
      "command": "/absolute/path/to/.venv/bin/clarity",
      "args": ["mcp", "--state", "/absolute/private/state", "--key-file", "/absolute/private/author.key", "--id", "REQ1"]
    }
  }
}
```

For Claude Code, use the same command/args under `mcpServers.clarity` in its MCP
configuration. For Codex, use its TOML MCP configuration:

```toml
[mcp_servers.clarity]
command = "/absolute/path/to/.venv/bin/clarity"
args = ["mcp", "--state", "/absolute/private/state", "--key-file", "/absolute/private/author.key", "--id", "REQ1"]
```

Client configuration may allow access to other tools or files. Review those
permissions in that client. Clarity's MCP server exposes three scoped tools:

| Tool | Behavior |
| --- | --- |
| `clarity_get_task` | Current selected requirement, sources, system instructions, JSON schema, version and context digest |
| `clarity_get_findings` | Current findings without repeating draft/evidence; `include_examples: true` requests expanded example diagnostics |
| `clarity_submit_result` | Author questions/draft or independent reviewer result; rejects stale versions/context |

Submission returns a compact receipt and findings. Retrieve diagnostics only when
needed. Author tasks default to a complete draft for a new requirement and targeted
revision when a draft exists. Clarity assembles and validates the complete revision
before fresh review. Append `--stage intake` for optional questions-only intake,
or `--stage draft` for a complete rewrite. Intake advice is not an approved requirement.

No key values appear in a task packet. The MCP process reads its designated private
key file. Never give it an operator key. Host-assistant inference is governed by
that client's subscription/call controls; Clarity records the submitted workflow
changes but does not invent local model-call charges for external conversations.

## Independent review

Start a fresh conversation with a separate configuration using `reviewer.key`.
A reviewer cannot submit a draft, answer owner questions or approve the handoff.
Review is bound to the current draft digest and context. Keep the writer's prior
self-evaluation out of the reviewer conversation.

The bridge does not sandbox either client against its OS user. Keep private state
and operator keys outside its accessible project/filesystem scope. A remote API
or assistant service may process selected evidence according to its own settings.

## Manual packet workflow

Download the task packet as author/reviewer. Give the packet's system instruction
and task to the chosen model, then paste its JSON into **Import assistant result
manually**. Submit from the same page version; refresh and regenerate if context
changes. An author result contains either questions or a draft, never both.
A reviewer result follows the review contract. There is no free-form-text bypass.
Author imports also accept the intake or targeted-revision contract from the selected
task packet. The original full-draft contract remains supported. Source/policy
changes reject old packets even when their workflow version has not changed.

Use one requirement per conversation. Read the supplied task and needed diagnostics;
there is no need to reread all ten profile files or every exported audit document.
Client conversation usage is outside Clarity's telemetry; see [efficiency](efficiency.md).

## Client references

- [VS Code MCP configuration](https://code.visualstudio.com/docs/agents/reference/mcp-configuration)
- [Codex MCP](https://developers.openai.com/codex/extend/mcp)
- [Claude Code MCP](https://code.claude.com/docs/en/mcp)
- [MCP tools specification](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)

Clarity implements newline-delimited JSON-RPC over stdio and protocol negotiation
for the listed current protocol versions. Actual client/account compatibility
still needs a smoke test in your installed client.
