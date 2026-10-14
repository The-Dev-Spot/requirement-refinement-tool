# Local workbench upgrade

This change addresses the audit's implementation and usability work. It preserves
the existing approval, independent-review and immutable-export boundaries.

| Audit area | Result |
| --- | --- |
| Recipient handover | Neutral current documentation; obsolete provenance reviews/placeholders removed; clean source-bundle command with checksums |
| Browser login | Same-origin referrer policy preserves browser-generated Origin; null/foreign/missing origins remain rejected |
| Outline parameters | Missing Examples references in step text, names, tables and Doc Strings are blocked; literal paired markup remains supported |
| Inference preflight | Exact packet checks precede reservation; atomic context check; rejected preflight is separately audited with no inference charge |
| Installation | Python package, console entry point, bundled quality resources, setup/doctor and installed-wheel CI smoke test |
| Configuration | Local model/assistant profiles, explicit optional cloud sharing, encrypted credential references, source connections and project policy |
| Working view | Progress, rule/example cards, coverage table, exact evidence passages, source impact and actionable findings |
| Model execution | Stage-specific JSON schema, bounded operational metrics, configurable output/keep-alive, background jobs and defined cancellation |
| Reads | Consistent query-only read transactions; mutations retain immediate reservations and version checks |
| Sources | Immutable library versions, metadata, read-only scoped imports, explicit selected attachment/replacement and applicability |
| Evaluation | 20 needs × 3 styles; repeated-trial/missing-output reporting; blind packets and human-rating sheet |
| Xray | Exact feature preservation plus explicit local edition/project/scenario mapping and pilot receipt validation |
| Recovery | Encrypted user-facing backups; all supported non-secret namespaces retained; fresh credentials and interrupted jobs after restore |
| Maintenance | Full Action commit pins, dependency update configuration and required-check guidance |

## Acceptance evidence still requiring the intended environment

Live assistant-client and model runs, actual source-service reads, browser/visual
review and a real Xray edition pilot require those installed clients, deployments
and authorized test accounts. No fabricated results or compatibility certification
are included. Human semantic labels and repeated quality trials remain necessary.

Repository settings are separate from code. Require review and passing checks in
branch protection/rulesets before merging. This change does not silently modify
repository administration or merge itself. Keep the release in review while the
remaining environment qualification is performed.
