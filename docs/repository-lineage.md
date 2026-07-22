# LineAlert repository lineage

## Current authority

`anthonyedgar30000/linealert-core` is the authoritative implementation repository for current LineAlert software.

Its merged `main` branch is the trusted code baseline. Active work is governed by the exact branch head, live pull-request metadata, exact-head CI, and the branch's `.project/active-work.json` state.

`anthonyedgar30000/helix-protocol-kernel` and `anthonyedgar30000/ContextOS` are active but separate boundaries. The protocol kernel owns governed evidence and transport contracts. ContextOS owns execution containment and policy enforcement. Neither repository is the LineAlert implementation lineage.

No legacy repository is current persistence, retrieval, lifecycle, diagnostic, or deployment authority merely because an earlier document assigned it that role. The root `README.md` and this lineage document must remain consistent.

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
