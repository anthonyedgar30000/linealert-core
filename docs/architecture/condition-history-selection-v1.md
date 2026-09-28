# Condition-history selection v1

This increment adds the read-only selection boundary required to use persisted condition history safely with persistent dependency localization.

The selector does not perform localization itself. It guarantees that the evidence handed to the existing localizer is explicit, bounded, complete with respect to the requested historian query, and not silently mixed across operating contexts.

## Typed condition history

`TimescaleHistorian.select_condition_history_records` reconstructs `ConditionHistoryRecord` values containing:

- observation time and ID;
- episode, asset, relationship, correlation, cycle, and phase identity;
- signal, value, unit, min/max envelope, temporal-rule status, quality, and reason code;
- topology from/to endpoints;
- source mode;
- operating context;
- clock evidence.

The record maps are detached and read-only after reconstruction.

## Exact filters

Condition history supports:

- asset ID;
- relationship ID;
- episode ID;
- cycle ID;
- phase ID;
- inclusive timezone-aware `from_time`;
- inclusive timezone-aware `to_time`;
- explicit limit from 1 through 5,000.

Results are queried newest-first with deterministic observation-ID tie breaking, then returned to callers in chronological order.

## Visible truncation

The historian requests `limit + 1` rows.

If more rows exist than the caller's explicit limit:

```text
truncated = true
truncation_semantic = older_matching_records_omitted
```

The typed selector preserves that state. Persistent localization refuses a truncated selection because omitted older samples could change:

- the first retained outside-envelope time;
- the earliest qualifying N-of-M window;
- the evidence available on related upstream/downstream relationships.

## Selection specification

`ConditionHistorySelectionSpec` requires:

- explicit selection label;
- exact asset ID;
- bounded limit;
- and either episode ID, cycle ID, or both `from_time` and `to_time`.

Optional phase and relationship filters remain valid for general history inspection.

## Localization handoff

`ConditionHistorianSelector.localize` adds stricter requirements before invoking `PersistentDependencyLocalizer`.

The handoff is refused when:

- the historian result is truncated;
- the result is empty;
- the requested target relationship is not present;
- the selected records contain more than one exact operating-context payload;
- the selection used `relationship_id`.

The relationship-filter refusal is deliberate. Persistent dependency localization needs the target relationship plus relevant upstream/downstream measurements from the same bounded history. Selecting only the target relationship would manufacture an incomplete dependency picture.

```text
target-only condition query
        -> valid history browsing
        -> NOT sufficient for dependency localization
```

The selector therefore asks the historian for the complete bounded condition selection and lets the deterministic topology/localization layer decide which relationships are relevant.

## Operating context

The selector preserves the exact persisted operating-context JSON. A localization handoff spanning different context payloads is refused rather than combining configuration/firmware/recipe conditions into one onset claim.

This does not certify that an empty or sparse operating-context payload is complete; it only prevents distinct retained contexts from being silently mixed.

## HTTP history surface

`GET /api/history/conditions` now accepts the same cycle/phase/time bounds used by typed selection:

```text
asset_id
relationship_id
episode_id
cycle_id
phase_id
from_time
to_time
limit
```

Time bounds are timezone-aware ISO 8601 values and inclusive.

The response includes:

- `count`;
- `truncated`;
- `truncation_semantic`;
- echoed `from_time` and `to_time`;
- chronological measurements.

A later read-only historian endpoint now consumes this selection contract and delegates admitted selections to the existing persistent localizer. The selector semantics in this document remain unchanged; HTTP does not replace or reinterpret them.

## Authority boundary

Condition-history selection does not:

- declare a physical fault;
- infer causation;
- decide that an observation is current physical truth;
- choose a persistence rule;
- change the persistent-localizer semantics;
- call CADGrounded;
- write to equipment;
- grant maintenance, engineering, production, or safety authority.

It is the evidence-completeness boundary between persisted relationship history and deterministic localization.
