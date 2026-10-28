# Start with Clarity

## 1. Open Clarity in your assistant

Open this repository in your AI coding assistant. Tell it:

> Use Clarity. Read AGENTS.md and help me with a requirement.

With Copilot, choose `story-intake` for a new requirement or `story-orchestrator`
for an existing story if your interface asks you to choose an agent. With Codex
or Claude Code, the request above points the assistant to the same instructions.
This repository supplies the workflow; you need an existing AI assistant to run it.

## 2. Describe what you need

You can start in ordinary language:

> Help me write a requirement. I want to export my personal reading list.

> Improve this requirement: [paste the text].

> Review DEMO-1234.

Use your actual issue key for a connected Jira project. You can begin with pasted
text without connecting Jira. Clarity asks one question at a time, then prepares
a concise draft and highlights what still needs deciding.

## 3. Review the draft

Read the proposed requirement and its open questions. Tell Clarity what to change.
It keeps detailed sources and review reasoning separately so the requirement stays
readable. It tells you when missing context or unavailable tools prevent a full
readiness check.

## 4. Decide what to post

Clarity waits for explicit approval before changing Jira. Its default review mode
posts the open questions as a comment after approval. Writing the proposed
requirement into the issue is a separate explicit choice, subject to the readiness
checks. You can keep working locally without posting anything.

See [everyday commands](../user-guide.md) when you need a specific action.

## Connecting your project

If your assistant is not already connected, ask the person maintaining your setup
to follow the [connection guide](../setup.md). It covers your own Jira project,
Confluence evidence area, and private connection settings. No Python application,
server, database, or dependency installation is needed for everyday use.
