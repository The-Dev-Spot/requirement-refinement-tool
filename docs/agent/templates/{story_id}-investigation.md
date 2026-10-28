# Investigation — {story_id}   (write-once)

Investigator-owned evidence from related Jira issues and relevant Confluence
children, collected between READ and EVALUATE. Treat borrowed facts as precedent:
mark each `[INFERRED from KEY]`, preserve provenance, and seek confirmation from
this story or an authoritative source before treating it as a requirement.

## Depth: LIGHT | DEEP  — {one-line reason}
<!-- LIGHT = rich, self-contained story: quick links + epic-sibling scan only.
     DEEP  = stub / clone / interface-data story / cluster member: full dig. -->

## Related issues considered
| Key | Status | Relationship | Kept? | Reason |
|-----|--------|--------------|-------|--------|
| DEMO-XXXX | Closed | clone-of / epic-sibling / link / component / text-match | yes/no | {why kept or excluded} |

## Reusable facts (with provenance)
<!-- Group by area: data model, interface contract, precedent ACs/Gherkin,
     glossary/terms, resolved ambiguities, risk precedent. -->
### {area}
- {fact}. `[DEMO-XXXX · {field} · {status} · last-updated YYYY-MM-DD]`
  <!-- add STALE if the source is old and rules may have moved -->

## Candidate answers to likely open questions
- **Likely OQ:** {question the evaluator/rewriter will probably raise}
  **Candidate:** {answer} `[INFERRED from DEMO-XXXX]` — confidence HIGH | MEDIUM | LOW
  (proposal only; the rewriter/PO confirms)

## Confluence child-page / data-dictionary check
<!-- For interface/data/stub stories: which cited/seed pages were traversed for
     children, and any data dictionary found. (L-0018) -->
- Parent {title} ({space} {id}) → child {title} ({space} {id}) — {what it held}

## Excluded / no-overlap
- {key} — {why it looked related but isn't}

## Summary for downstream stages
{2–4 lines the evaluator and rewriter should carry forward.}
