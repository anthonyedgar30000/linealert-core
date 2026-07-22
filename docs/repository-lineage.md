# LineAlert repository lineage

## Current authority

`anthonyedgar30000/linealert-core` is the authoritative implementation repository for current LineAlert software.

Its merged `main` branch is the trusted code baseline. Active work is governed by the exact branch head, live pull-request metadata, exact-head CI, and the branch's `.project/active-work.json` state.

`anthonyedgar30000/helix-protocol-kernel` and `anthonyedgar30000/ContextOS` are active but separate boundaries. The protocol kernel owns governed evidence and transport contracts. ContextOS owns execution containment and policy enforcement. Neither repository is the LineAlert implementation lineage.

No legacy repository is current persistence, retrieval, lifecycle, diagnostic, deployment, or equipment-control authority merely because an earlier document assigned it that role. The root `README.md`, this lineage document, and `.project/active-work.json` must remain consistent.

## Merged implementation and governance history

PR #12, **Assess replay timing against governed baselines**, is merged implementation reality at commit `a1812ff69ef6cb05031bced9f4dc7577c6ae8d2a`.

The merge does not erase its recorded governance defect. Before merge, the PR body and branch project state marked it blocked by overlapping ownership with PR #11 and explicitly prohibited merge until that collision was resolved. Its successful CI established test results for the inspected code; it did not satisfy the blocked authorization gate.

PR #11 was later closed without merge because its head was obsolete and conflicted with the merged PR #12 project-state paths. Future work must start from current `main` rather than merging either obsolete branch state.

```text
merged_implementation != governance_gate_satisfied
green_ci != authorized_merge
repository_state != deployment_state
```

## Design archaeology

The following repositories preserve useful history but are not current implementation authority:

### `anthonyedgar30000/LineAlertDemo`

This is a legacy prototype containing earlier demo assumptions and mixed architecture.

Open PR #2 and PR #3 are non-current prototype work. They must not be merged into the current LineAlert lineage or copied wholesale into `linealert-core`.

A useful idea, fixture, simulator behavior, or test may be selectively reimplemented only through a new bounded `linealert-core` branch that:

- names the extracted source and preserves attribution;
- restates current LineAlert authority boundaries;
- rejects arbitrary causal-confidence claims;
- adds focused deterministic tests;
- preserves source, asset, timestamp, clock, quality, engineering-unit, calibration, configuration, and topology semantics where applicable;
- receives exact-head CI and governed review before merge.

### `anthonyedgar30000/linealert-analysis-engine`

This is a legacy placeholder rather than an active analysis implementation. Open PR #1, **Implement Phase 1 backend analysis**, is non-current prototype work. It must not be merged into the current lineage or copied wholesale into `linealert-core`.

Its ideas may be considered only through the same bounded migration rule, with special review of persistence contracts, confidence terminology, event identity, engineering units, timestamp quality, topology applicability, evidence provenance, and causal claims.

### `anthonyedgar30000/HelixMemoryService`

This is an early memory-service prototype and outdated architecture reference. It may inform future persistence design, but it is not current LineAlert persistence, retrieval, or lifecycle-system authority and must not be copied wholesale.

A future persistence boundary requires a separately governed current architecture, explicit package and data contracts, provenance and supersession behavior, tests, deployment evidence, rollback, and review.

## Migration rule

Historical code or ideas become current only after they are deliberately re-derived inside the authoritative repository under a bounded scope with current contracts, tests, verification, review, and rollback.

```text
historical_pattern != current_root_cause
prototype_behavior != approved_product_behavior
copied_code != verified_current_design
successful_test != safe_production_change
```
