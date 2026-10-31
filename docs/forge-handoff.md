# Clarity → Forge typed requirement handoff (v2)

This is a **local, versioned handoff contract**, not an agent orchestration service. The Clarity toolkit creates an export from an *already reviewed* requirement; Forge imports it into its existing governed planning pipeline. **Both repositories remain usable independently.** No connector call, code generation, tool approval, source write or production access is authorized by an export, even if someone supplies the word `approved`.

## Use the right acceptance format

| Type | Format | Example |
|---|---|---|
| Behavioral change or bug | `acceptance.feature` with declarative Gherkin and named `@case_<id>` scenarios **plus** `criteria.json` | A duplicated backend event creates exactly one job |
| Refactor/architecture | Typed `criteria.json` only | Preserve existing public behavior and an identified invariant |
| Infrastructure/operations | Typed `criteria.json` only | At most two workers per pool, reserved critical slot, recoverable leases |
| Migration | Typed `criteria.json` only | Preexisting records remain valid; rollback/recovery is observable |
| Research/spike | Typed `criteria.json` only | Produce a sourced comparison and decision report; no implied code change |

For each criterion, include a stable ID, `kind`, measurable `text`, evidence approach (`verification`) and `scenario_id` (same ID for behavioral criteria, otherwise `null`). The exact reviewed `requirement.md` remains separate. Gherkin **syntax and tag matching are not executed acceptance tests**: implementation and independent verification are Forge's responsibility.

## Package format v2

Deterministic ZIP with flat UTF-8 files and explicit SHA-256 digests:

- Both kinds: `requirement.md`, `criteria.json`, `handoff.json`.
- Behavioral kind also includes `acceptance.feature`.
- `handoff.json` carries strict `schema_version: 2`, `kind: clarity-portable-handoff`, immutable story/revision, `story_type`, source system/reference, ordered criterion IDs and file digest map.
- No tool, production/criticality, model, permission or credential fields. Archive size and file counts are bounded. Source-reference and hash only prove data consistency, **not sender identity, authorized approval or independent review**.

Example `criteria.json`:

```json
{
  "schema_version": 2,
  "story_type": "non-behavioral",
  "criteria": [
    {
      "id": "AC-1",
      "kind": "operational",
      "text": "Only one normal and one reserved critical worker may run in each pool",
      "verification": "Observe four controller leases under a mixed synthetic load",
      "scenario_id": null
    }
  ]
}
```

For a behavioral story set `story_type: behavioral`, each criterion `kind: behavior` and `scenario_id` equal to its `id`. Add a `.feature` with one `@case_AC-1` tag preceding the corresponding scenario. Do not create fake Gherkin to satisfy a transfer protocol.

## Local export

```sh
python3 scripts/export_forge_handoff.py \
  --requirement /private/reviewed/requirement.md \
  --criteria /private/reviewed/criteria.json \
  --story-id HOM-123 --revision 2 \
  --source-system linear --source-ref HOM-123 \
  --output /private/reviewed/HOM-123-v2.zip

# Behavioral criteria: additionally supply
# --feature /private/reviewed/acceptance.feature
```

The command never overwrites output. Review and classify the *actual source* before exporting. Do not put PII, secrets or internal business evidence in archives that will be shared; only reviewed developer-facing text should be exported. The exporter validates document shape, identity, hashes and tag references; it **cannot know whether the underlying business decision was approved**, whether a Gherkin scenario is executable or whether external standards were adopted.

## Forge consumer and status

Forge imports with its [existing portable handoff process](https://github.com/The-Dev-Spot/forge/blob/main/docs/agent/portable-handoffs.md), including SHA-256 explicit local acceptance. Forge v1 packages are unchanged and remain accepted. Forge v2 maps each criterion ID to locked success criteria and review evidence. Statuses are structural, not semantic authorization; a real model-powered implementation and independent checker must still run under host-controlled policy.

For automated Forge City use, attach trusted operator-approved WorkOrder identity **outside this archive**. Clarity must never decide repo permission, critical lane eligibility or run budget based on untrusted ticket content. That part is separately tracked in [HOM-1977](https://linear.app/sashafelix-homelab/issue/HOM-1977).

## Rollout gates

1. Unit tests for behavioral / non-behavioral packaging and mutation rejection.
2. Real cross-repository exported fixture → Forge inspect → verify → delivery-plan mapping; compare immutable criterion IDs.
3. Three-story live study (backend bug, infra reliability, refactor) and independent actual test evidence.
4. Only after these, connect accepted tracker issues into unattended Clarity and Forge worker pools.
