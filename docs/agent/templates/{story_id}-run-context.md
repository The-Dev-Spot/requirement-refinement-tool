# Run Context — {story_id}

```
story_id:        {DEMO-XXXXX}
date:            {YYYY-MM-DD}          # set at run start; never invent later
source:          {Jira URL or "pasted"}
story_type:      {behavioral | non-behavioral}
mode:            {review | apply}      # set at run start; cannot change mid-run
initiative:      {initiatives[*].label from project-config.yaml | none}
current_stage:   {evaluate | rewrite | quality_gate | awaiting_approval | done | failed | rejected}
gate:            {PASS | WARN | FAIL | pending}
grounding:       {Confluence pages / Reference docs consulted}
```

## Scope
- In: {...}
- Out: {...}

## Notes
{anything a later stage or reader needs that is not obvious from the story}
