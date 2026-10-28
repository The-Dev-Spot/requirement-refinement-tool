# Shared step catalog

This folder holds the **canonical Gherkin step phrasings** used across stories.
Its single job is **anti-fragmentation**.

## The problem it solves

When many people (and agents) write Gherkin independently, the same behavior ends
up phrased ten different ways:

```
When the application is submitted
When a request is sent for assessment
When the analyst submits the request
Given the customer applied for the service
```

Fragmentation is expensive for us and risky for **handover to the receiving
team**:

- the receiving team can't tell whether two differently-worded steps mean the
  same thing (do they build one behavior or two?);
- step definitions and tests multiply needlessly;
- reviewers can't spot a missing scenario when every story speaks its own dialect.

A shared catalog gives everyone **one agreed way to say each thing**, so a
scenario reads the same whoever wrote it, and a stranger reading cold sees
consistent language.

## How to use it

1. **Reuse before you write.** Before authoring a new `Given`/`When`/`Then`,
   look in [`catalog.md`](./catalog.md) for a canonical step that fits, and use
   its exact wording. `story-eval`'s `L8` check flags near-duplicates that drift
   from the catalog (advisory WARN — see `rubric/definition-of-ready.md`).
2. **Add deliberately.** If no catalog step fits, write a new one **declaratively**
   (describe behavior/outcome, never UI clicks — see `docs/adr/0001-gherkin-as-ac-format.md`)
   and propose adding it to `catalog.md`. New steps are a small, reviewed change,
   not a free-for-all.
3. **Parameterize, don't multiply.** Prefer one parameterized step
   (`the <segment> application`) over near-identical variants.
4. **Keep it business language.** Steps describe domain behavior (orders,
   customers, interfaces, service coverage), not implementation detail.

## What a good catalog entry looks like

- Declarative and outcome-focused.
- Reusable across stories (parameterized where it helps).
- Named in the domain's own terms (customer, booking, order status, coverage plan).
- Free of vague terms (it must pass the rubric's `L3` check too).

See [`catalog.md`](./catalog.md) for the seed set and add to it as patterns
recur.
