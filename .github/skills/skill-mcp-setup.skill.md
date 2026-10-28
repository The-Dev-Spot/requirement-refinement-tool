# Skill: skill-mcp-setup

## Purpose
Verify the host's configured Jira/Confluence tools before a stage depends on them.
No bundled organization-specific CLI, endpoint, header or authentication scheme is assumed.

## Reads
- AGENTS.md and the public project-config example plus ignored local override.
- The host's advertised connector capabilities and its documentation.
- Only operator-selected project/space/issue identifiers.

## Steps
1. Confirm the configured base URLs, project/team scope and knowledge spaces.
   Stop remote operations for null values, fictional DEMO keys or example.invalid URLs.
2. Check that the required read/search operations exist. Authenticate through
   the configured connection; never ask the model to find, echo or commit tokens.
3. Read one authorized target and verify key, scope, important fields and source version.
   Distinguish inaccessible content from an empty field or missing requirement.
4. Verify the connector's rendering and custom-field shapes before enabling a write.
   Use only the operations allowed by AGENTS.md and its explicit approval gate.
5. Verify a configured log-book root and read-back support separately. All other
   knowledge pages stay read-only. Never claim successful publication from a tool list alone.
6. Record pass/blocked/NOT_RUN per capability in the run context. Missing tools or
   configuration block dependent remote stages; local drafting may remain staged.

## Guardrails
Do not overwrite global IDE settings, persist credentials or install another tool
as an automatic side effect of checking setup. Never weaken host approval controls.
No silent REST fallback across an unapproved endpoint or scope.
