# MCP setup — Jira and Confluence

Configure an authorized Jira/Confluence connector in the assistant you use.
Server names, authentication, tool names, endpoint shapes and client configuration
formats depend on your connector and edition. The empty `.github/mcp.json.example`
is a starting container, not a preconfigured server or an invitation to discover credentials.

Keep `.github/mcp.json`, host settings and any tokens private. Do not put tokens
in prompts, run artifacts, GitHub issues or shell output. Verify the server against
its own documentation. Do not assume a proprietary header or server URL.

## Verify capabilities

1. Read one explicitly selected issue: title, description, actual AC field,
   comments and source update/version. Confirm the returned project/key.
2. Read one permitted knowledge page and its last-modified metadata.
3. Confirm which tools support scoped issue search, related issues, child-page
   traversal, comments, description/AC updates and issue creation. Record missing capabilities.
4. For the log book, verify an operator-configured evidence root separately.
   Never edit grounding/spec pages. Retain verify-before-write and idempotent page IDs.

Use `skill-mcp-setup` before MCP-dependent skills. Do not claim readiness on an
unperformed test. No startup Python service or corporate CLI is required.

## Rendering is connector-specific

The source workflow's Markdown/wiki conversion and checklist-object rules remain
documented in skill-jira-io. Verify the installed Jira edition and field plugin
before using them: Jira Cloud may require a structured document body, while a
Server/DC installation may accept wiki markup. A mismatch stops the write and
keeps the staged Markdown evidence. Never discard fields to force a request through.

Configure project identifiers in the ignored local project-config override. With
pasted/local evidence, missing integrations are explicit limitations rather than
fabricated URLs, remote writes or successful log-book publication.
