# Functional-temporal historian selection v1

This increment adds a read-only, time-addressable selection layer over persisted functional-temporal evidence.

It does not decide which historical interval is "commissioned truth." A caller must explicitly label and bound each selection before records are handed to the commissioned-vs-selected-time comparator.

## Selection contract

A selection requires:

- an explicit label;
- an exact asset ID;
- a bounded record limit;
- and either an episode ID, a cycle ID, or both a timezone-aware `from_time` and `to_time`.

Optional filters are:

- phase ID;
- record kind;
- episode ID;
- cycle ID;
- inclusive `from_time`;
- inclusive `to_time`.

Time bounds must be timezone-aware ISO 8601 values. An inverted interval is rejected.

## Typed historian reads

`TimescaleHistorian.select_functional_temporal_records` reconstructs exact `FunctionalTemporalHistoryRecord` objects from the historian row, including:

- record/cycle/episode identity;
- record kind and epistemic state;
- evidence validity and temporal coverage;
- phase/transition/requirement identity;
- transition disposition;
- exact asset/component/profile/mode/configuration/firmware/calibration/sampling context;
- recipe/product/context tags;
- evidence IDs;
- reasons;
- clock evidence;
- source details/provenance.

Records are returned in deterministic chronological order.

## Visible truncation

The historian queries `limit + 1` records so it can determine whether the requested selection is complete.

When a selection exceeds its explicit limit:

```text
truncated = true
truncation_semantic = older_matching_records_omitted
```

The selector refuses to hand a truncated reference or selected-time window to the comparison layer. It never compares a hidden partial history.

This is deliberately different from silently clipping a large query and treating the result as complete.

## Comparison handoff

`FunctionalTemporalHistorianSelector` selects both sides independently.

```text
explicit reference spec
        -> typed historian selection
        |
explicit selected spec
        -> typed historian selection
        |
both complete?
   no  -> bounded selection refusal
   yes -> #132 comparator unchanged
```

The labels supplied by the caller are passed directly into the comparison result. The selector does not rename a selection to "commissioned" or promote it to commissioning authority.

## HTTP history bounds

`GET /api/history/functional-temporal` additionally accepts:

- `from_time`
- `to_time`

Both are inclusive timezone-aware ISO 8601 bounds.

The response reports:

- `count`
- `truncated`
- `truncation_semantic`
- echoed `from_time` / `to_time`
- the selected records

Malformed query bounds are client errors, not historian outages.

## Authority boundary

The selection layer does not:

- infer commissioning approval;
- choose a reference window automatically;
- aggregate repeated reference observations;
- hide truncation;
- alter evidence validity;
- convert historical similarity into causation;
- make a diagnosis;
- call CADGrounded;
- write to equipment;
- grant maintenance, production, engineering, or safety approval.

It only selects exact persisted evidence for governed comparison.
