# Functional-temporal comparison presentation v1

This increment exposes the governed historian selector and commissioned-vs-selected comparator to the technician-facing Operator View without moving comparison logic into the browser.

It is a stacked increment on the historian-selection work. The UI is read-only and depends on that backend selection contract.

## Technician flow

```text
persisted functional-temporal history for exact asset
        ↓
recent cycle candidates
        ↓
technician explicitly chooses:
  REFERENCE CYCLE
  SELECTED CYCLE
        ↓
Compare selected cycles
        ↓
historian selector
        ↓
comparison admission / refusal
        ↓
bounded difference presentation
```

The reference picker starts empty. LineAlert does not choose a commissioning reference automatically.

When the investigation handoff already carries a current correlation/cycle ID and that ID exists in persisted functional-temporal history, it may be preselected only as the selected/current investigation cycle. That hint is not a reference designation and does not establish physical state.

## Backend authority

The browser never implements context compatibility, truncation policy, epistemic admission, or metric-delta logic.

`GET /api/history/functional-temporal/compare`:

1. parses two explicit prefixed selection specifications;
2. reads each selection through the historian selector;
3. refuses either side if the selection is truncated;
4. executes the existing comparator unchanged;
5. serializes its exact disposition, refusals, points, first-divergence timestamps, and source metric deltas.

The Next.js routes only proxy the historian service.

## Candidate cycle list

The Operator View asks the historian for up to 5,000 recent functional-temporal records for the exact asset and groups those records by cycle ID to populate the two selectors.

This candidate list is navigation only. It is not the comparison evidence set.

If the candidate read itself is truncated, the UI says so. When the technician requests a comparison, the backend independently re-reads both selected cycles with their own limits and refuses a truncated comparison selection.

## Displayed result

For an admitted comparison, the technician sees:

- count of changed semantic identities;
- unresolved comparison count;
- earliest retained divergence timestamp;
- changed guard/invariant/transition/phase identities, earliest divergence first;
- reference and selected epistemic states;
- retained numeric source delta when present;
- the comparator claim boundary.

The compact v1 panel displays the earliest six changed semantics while retaining the backend's total changed count. This is a presentation cap only; it does not alter the comparison result.

For a refused comparison, the technician sees the backend refusal detail and any mismatched context fields. The UI does not attempt a fallback comparison.

## Single next action

The interaction deliberately presents one material action:

`Compare selected cycles`

Reference/selected choices are evidence selection, not equipment actions.

## Authority boundary

The presentation layer does not:

- designate a cycle as commissioned truth;
- compare records in TypeScript;
- override historian truncation;
- hide comparator refusals;
- translate difference into root cause;
- infer mechanical state;
- call CADGrounded;
- recommend or authorize an equipment change;
- grant maintenance, engineering, production, or safety approval.

It makes the deterministic evidence difference legible to a technician while preserving the backend authority boundaries.
