# The developer-and-tester handoff standard

**The final requirement is the product.** A user's experience changes how Clarity
elicits the need, not what the development team is entitled to receive.

## Mandatory evidence

Every handoff contains source-linked problem, business value, scope, exclusions
and rules. Relevant definitions, dependencies and non-functional constraints are
also recorded and reviewed for applicability. The authoritative request and owner
decisions can support statements directly. Other references need an explicit
applicability decision. Source hashes and exact quotations detect stale or invented
passages; independent semantic review determines whether the passage supports the
statement. Neither a hash nor a lengthy rationale proves that judgment is correct.

## Acceptance criteria

Gherkin is canonical, not an optional alternative to a final checklist. Supporting
prose explains context; scenarios express observable acceptance outcomes. The
legacy v0.2 checklist API remains readable for compatibility but does not satisfy
this handoff contract.

Each Scenario or Scenario Outline has one direct `@case_ID` tag, a unique name,
context, action and outcome. Rules, Backgrounds, Doc Strings, Data Tables and
example rows are preserved by keeping the original feature text. The official
parser/compiler checks actual grammar; context/action/outcome and stable IDs are
additional Clarity quality policies. Blank or unexpanded outlines cannot hide
behind another valid scenario. Lexical heuristics currently support English only.

Each rule/constraint has explicit positive, negative, boundary and alternative
coverage. These are applicability questions, not a mandated scenario count.
Inapplicable categories require a substantive reason and independent review;
every rule must still have at least one scenario. Stable scenario IDs link the
coverage matrix to the actual parsed scenarios, not a parallel unverified list.

## Reviewer responsibilities

The reviewer receives the draft and sources without a writer self-score. It checks
intent, cold-read independence, precision, scope, unsupported additions, observable
outcomes, dependencies, non-functional constraints, applicability and coverage.
Every statement and scenario receives a separate support/fidelity judgment. The
counterexample challenge asks whether materially different implementations could
both satisfy the wording. Any unresolved material ambiguity blocks the handoff.

A context-sensitive phrase is not automatically an error. A reviewer can justify
an exact wording warning, such as a keyboard interaction that is itself required
behavior. Objective failures cannot be reclassified as warnings. An operator can
record that a particular instruction detector hit is benign; this is scoped to
the exact draft and context, never permission for unrestricted tools or publication.

## Export contract

The operator sees and approves the exact plan and hashes. The bundle contains
`requirement.md`, `acceptance.feature`, `traceability.json`, `sources.json`,
`quality-review.json`, import notes and a manifest. The feature bytes—including
line endings—are the same bytes approved as acceptance criteria. There is no
second-model test-case rewrite. Only approved bundles can be obtained from the
controller's export route; repeated retrieval returns the stored bundle.

The Cucumber, Xray Cloud and Xray Server/DC profiles identify the intended import
route, not live compatibility certification. Import **only acceptance.feature**;
other bundle files may contain private source evidence. Tracker keys, project
settings, required custom fields, existing-test mappings and repeat-import behavior
must be validated in the selected instance before operational use. No remote
mutation or automatic requirement linking is implemented.

## Official implementation references

- Gherkin reference: https://cucumber.io/docs/gherkin/reference/
- Official parser/compiler: https://github.com/cucumber/gherkin
- Xray Cloud feature import: https://docs.getxray.app/space/XRAYCLOUD/44577091/Importing%2BCucumber%2BTests%2B-%2BREST%2Bv2
- Xray Server/DC feature import: https://docs.getxray.app/space/XRAY/301698724/Importing%2BCucumber%2BTests%2B-%2BREST

These document the underlying formats and import workflows. They do not establish
that this implementation has passed a live Xray round-trip. Feature specifications
also need matching step definitions before they become executable automation.
