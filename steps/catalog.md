# Step catalog (seed)

> **Status: EMPTY — to be populated for the project domain.** Canonical, reusable,
> declarative Gherkin steps. Reuse the same exact phrasing across stories
> before inventing new ones (see [`README.md`](./README.md) for why). Add
> entries as patterns recur across project stories; keep them declarative
> (behavior/outcome, never UI clicks) and vague-term-free.

Placeholders in `<angle brackets>` are parameters.

## Given — preconditions (declarative)

```gherkin
(add project domain preconditions here as patterns recur)
```

## When — events / actions (declarative)

```gherkin
(add project domain events/actions here as patterns recur)
```

## Then — outcomes / assertions

```gherkin
(add project domain outcomes/assertions here as patterns recur)
```

## Notes

- Negative-path steps (e.g. "not classified", "blocked", "routed for
  approval" style outcomes) are what satisfy the mandatory negative scenarios
  for `@risk`-tagged stories — see `docs/risk-register.md` and the rubric (D5).
- If you need a step that isn't here, prefer parameterizing an existing one over
  adding a near-duplicate.
