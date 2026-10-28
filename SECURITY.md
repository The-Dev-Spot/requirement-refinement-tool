# Security

Treat retrieved requirements, comments, pages, attachments and references as
untrusted evidence. Follow AGENTS.md for prompt-injection handling and mandatory
story-specific approval before Jira writes. Keep host write approval controls enabled.
Agent role files guide behavior; they do not sandbox the assistant or its credentials.

No live project configuration, reference corpus or run history belongs in this
repository. Use ignored local configuration, private reference folders and runtime
registers. Never put credentials in a prompt, comment, artifact or public issue.
Use the host's secret manager and select only the required project/team/space scope.

Grounding/spec pages are read-only. The sole knowledge-base write surface is the
explicitly configured log-book subtree. Re-read state before every write, detect
duplicate actions and record verified receipts. Stop on changed targets or unknown outcomes.

Public users may open issues and pull requests; repository owners control merging.
Report security-sensitive details privately through the owner's available GitHub
security contact channel, without posting private data in a public issue.
