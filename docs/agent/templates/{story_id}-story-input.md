# Story Input — {story_id}   (write-once)

## As received (verbatim from Jira)

### Core
- **Title:** {...}
- **Status:** {...}
- **Priority:** {...}
- **Assignee:** {...}
- **Reporter:** {...}
- **Labels:** {...}
- **Created / Updated:** {...}

### Description
{full description text}

### Acceptance Criteria Checklist (custom field — see `custom_fields.ac_checklist`, if configured)
- [ ] {checklist item 1}  (mandatory: yes/no)
- [ ] {checklist item 2}  (mandatory: yes/no)
- ...

### Acceptance Criteria — legacy (custom field — see `custom_fields.ac_legacy`, if configured)
{include if populated, otherwise omit section}

### Comments
{include recent comments — they often contain clarifications, implementation
notes, and decisions that affect the story's meaning}

### Attachments / embedded images
{list attachments; if the description references images, note them here and
describe what they show — screenshots of UI, XML schemas, data flow diagrams}

### Links
- **Parent:** {epic or parent link, if this project has a dedicated field}
- **Related:** {linked issues — blocks, is-blocked-by, relates-to}

### Metadata
- **Feature Team:** {if configured — see `custom_fields.feature_team`}
- **Categorization:** {if configured — see `custom_fields.categorization`}
- **Region:** {if configured — see `custom_fields.region`}
- **Request Source:** {if configured — see `custom_fields.request_source`}
- **SW Development:** {if configured — see `custom_fields.sw_development`}
- **Test Status:** {if configured — see `custom_fields.test_status`}

> **Read rule:** always fetch with `fields=*all` and `comment_limit=10`.
> The full story is description + AC checklist + comments + attachments + links + metadata.

## Gathered context (with provenance)
Each item cites its source so downstream stages can satisfy rubric `D6`.

- {claim / rule / number}
  > Source: {title}, {section}, last-modified {YYYY-MM-DD} ({url-or-id})

## Applicable risks (from docs/risk-register.md)
- {RISK-xxx — why it applies}
