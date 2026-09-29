# Clarity roadmap — quality first

## North star

Deliver excellent, developer-ready requirements with precise Gherkin acceptance
criteria regardless of whether the request starts with a senior analyst, junior
analyst or someone with no analysis experience. Test management reuses those exact
approved scenarios. Clarity is standalone; no development-pipeline integration.

## Delivered in this change

Raw-brief intake; traceable statements; exact source quotes and applicability
attestations; trusted policy; rule-to-scenario coverage; independent statement and
scenario review; governed false-positive handling; bounded opt-in model stages;
interactive loopback UI; immutable Gherkin handoffs; same-need evaluation harness;
versioned backup/restore. The ten specialist definitions are retained. See the
quality-handoff record for what was tested and what is not claimed.

## Next acceptance work

**Dogfood the complete flow.** Choose an authorized local model deployment and run
real, anonymized needs through ordinary-language intake, source confirmation,
questions, review and approval. Record failed steps and human corrections. Do not
replace independent review with a writer's self-score to make a demonstration pass.

**Human-labelled quality benchmark.** Expand beyond the three synthetic starting
points to varied needs, ambiguity, conflicting evidence, security and nonfunctional
requirements. Blind developer/tester reviewers assess final outputs; use multiple
trials and per-group results. Measure unsupported statements, missed decisions,
false blocks, scenario coverage and correction effort. Equal quality is the target,
not a conclusion established by unit tests.

**Xray edition pilot.** Select Cloud or Server/Data Center and a test project.
Validate .feature imports, outlines, backgrounds, tags, traceability and repeated
import behavior. Preserve exact Gherkin bytes. Project/requirement/Test-key mapping
requires explicit configuration; never infer it. A feature file is not executable
automation until its step definitions and environment exist.

**Broader source handling.** Add permission-aware read adapters and immutable
source revisions with original/effective/retrieval dates. Preserve authority and
scope. Changes must identify affected claims rather than silently rewriting an
approved baseline. Current text captures attest applicability but do not validate
remote source identity or authorship automatically.

**Usability and supported deployment.** Test the workbench with novice users as
well as experienced analysts; remove unnecessary JSON handling. Current model
contracts may need constrained-output improvements based on actual failures.
Public hosting, SSO, per-project reviewer permissions, Windows ACL support,
packaging and encrypted backups require explicit engineering and security reviews.
Do not expose the loopback server as a production multi-tenant service.

**Measured orchestration improvements.** Compare the two-stage runner with selected
specialist dispatch, asking whether the extra stage improves the final requirement.
Add a stage only when quality results justify its time/cost. No automatic external
publication, learning promotion, custom-model training or infrastructure expansion
without a demonstrated need and separate approval.
