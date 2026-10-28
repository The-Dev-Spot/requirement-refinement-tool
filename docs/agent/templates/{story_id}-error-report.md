# Error Report — {story_id}   (create-on-failure)

Written by `story-orchestrator` when a stage fails; the run halts.

- **Stage:** {evaluate | rewrite | quality_gate}
- **What failed:** {...}
- **Evidence:** {exact error / offending text / missing input}
- **Attempted fix:** {and result — one retry max for transient tooling}
- **Next actions:** {what a human should do to unblock}
