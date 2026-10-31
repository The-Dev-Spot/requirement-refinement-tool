# Clarity

Turn a rough idea into a clear, concise requirement that a team can build.
Clarity asks the right questions, checks the available context, and helps you
spot gaps before work starts.

## Get started

Open this repository in your AI coding assistant and tell Clarity what you need:

> Help me write a requirement: I want to export my personal reading list.

> Review this requirement and tell me what is missing: [paste your text]

> Review DEMO-1234.

Clarity will guide you one question at a time. You do not need to choose its
internal stages or learn the names of its agents. `DEMO-1234` is a fictional key;
use your own project key when Jira is connected.

Start with the [quickstart](docs/agent/QUICKSTART.md). You can begin with pasted
text; [connecting Jira and Confluence](docs/setup.md) is a separate setup step.
No Python application or server installation is required.

## Standards-aware requirement refinement

Clarity includes a [public engineering standards library](Reference/standards/README.md)
covering requirements quality, secure coding and APIs, privacy, UX/accessibility
and operational reliability. It selects **only relevant** guidance per story and
uses the existing [Definition of Ready](rubric/definition-of-ready.md) D1–D10;
it does not force every standard onto every ticket or certify code quality.
Published sources and versions live in [the catalog](Reference/standards/catalog.yaml).

## What you get

- A short requirement with the goal, scope, and clear acceptance criteria.
- Questions where a decision or missing detail is still needed.
- A separate review record with the sources and reasoning behind the requirement.
- Control over what gets posted: Clarity asks for explicit approval before changing Jira.

Behavioral requirements use Given/When/Then examples. Other work uses measurable
completion checklists. Clarity targets 3–6 acceptance criteria, with a maximum of
8. It keeps the requirement concise without dropping details needed to build and
test it. See the [fictional examples](examples/lean-requirement.md).

## Optional Forge handoff

Reviewed requirements can be exported as typed, exact-byte portable handoffs for
[Forge](https://github.com/The-Dev-Spot/forge). The [handoff guide](docs/forge-handoff.md)
explains when to use Gherkin (behavioral examples) versus measurable checklist
criteria (infrastructure, refactors and research), stable IDs and the
deterministic local exporter. This is **data transfer**, not automatic dispatch,
test verification, Jira write approval or permission to change production.

## Use Clarity your way

Review an existing story, develop a new requirement through conversation, or
break a larger specification into smaller proposed stories. By default, an
approved review posts questions as a comment. Updating the requirement itself
requires the appropriate explicit approval and readiness checks. Nothing is
posted just because a draft looks ready.

[Everyday commands and approvals](docs/user-guide.md) ·
[Connection setup](docs/setup.md) · [Privacy and security](SECURITY.md)

## For maintainers

Clarity contains 10 agent profiles, 11 reusable skills, the Definition of Ready,
and neutral templates. The full investigation, evaluation, rewrite, quality gate,
and PO feedback workflow is retained. Missing tools or checks are reported;
a draft is never described as verified when a required check could not run.

[Operating rules](AGENTS.md) · [Agents](.github/agents/README.md) ·
[Skills](.github/skills/README.md) · [Readiness rubric](rubric/definition-of-ready.md) ·
[Contributing](CONTRIBUTING.md)

The separate [clarity-end-goal](https://github.com/The-Dev-Spot/clarity-end-goal)
repository preserves the full standalone Python application and its development
setup. It is not required to use this Clarity toolkit; its access permissions are
separate.
