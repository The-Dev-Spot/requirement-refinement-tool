# Agent catalog

These are versioned role specifications, not autonomous background workers.
All roles inherit `AGENTS.md` and have no external write permission in this baseline.

| Role | Responsibility |
| --- | --- |
| story-orchestrator | Existing-story run ownership, transitions and approval staging |
| story-intake | New requirement interview, duplicate check and full pipeline parity |
| story-investigator | Bounded, provenance-preserving investigation |
| story-evaluator | Classify work and assess D1–D10 with L1–L8 evidence |
| story-rewriter | Improve the draft without inventing requirements |
| story-quality-gate | Independently assess the final artifact |
| story-po-analyst | Look for evidenced answers before burdening the owner |
| story-po-challenger | Challenge, sharpen and consolidate necessary questions |
| story-po-responder | Incorporate authorized answers into a new local revision |
| story-creator | Propose an evaluated specification breakdown |

Review starts with orchestrator; new intake starts with intake; specification
breakdown starts with creator. All other direct entry requests redirect to one
of those. Intake and orchestrator may call the same analysis roles. PO response
handling returns to the quality gate and approval, never straight to publication.
