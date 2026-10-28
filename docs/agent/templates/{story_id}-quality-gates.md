# Quality Gate — {story_id}   (replace-in-place)

Final story scored: {rewrite.md | original}. Re-scored gate: {PASS | WARN | FAIL}.

## VERDICT: {READY | NOT READY} for handover

## Handover-readiness matrix
- [ ] Overall gate is PASS
- [ ] Zero unresolved `# OPEN QUESTION -> PO:` markers
- [ ] D1 cold-read passes on Jira payload alone; essential build facts remain there
- [ ] D3 ACs format-appropriate (declarative Gherkin or measurable checklist)
- [ ] D5 every @risk has its mandatory negative scenario
- [ ] D6 every sourced claim has provenance with last-modified in review evidence
- [ ] D10 regulated flow carries audit/compliance criterion

- [ ] L9 ≤8 ACs; target 3–6, outline counts once
- [ ] L10 converted payload measured: ≤20,000 chars (WARN >10,000; target ≤8,000)
- [ ] Checklist item length measured (WARN >250 chars)
- [ ] Required checks actually executed; no NOT_RUN treated as PASS
- [ ] Full rationale/sources are in review notes, and payload links to evidence

## Blockers (if NOT READY)
- {blocker + which matrix item / rubric id}

## Evidence
- {links to eval-report.md, rewrite.md, source citations}
