# Technician sustained-deviation presentation v1

This increment exposes configured persistent-localization evidence in the Operator View without adding any browser-side diagnostic or persistence logic.

## Data path

```text
Operator View investigation handoff
        ↓
GET /api/historian/conditions/localize
        ↓
Next.js read-only proxy
        ↓
historian configured-policy localization endpoint
        ↓
Sustained Deviation card
```

The browser supplies only the exact investigation identity already present in the handoff:

- asset ID;
- target relationship ID;
- episode ID;
- a bounded historian limit.

The browser does not supply `required_outside` or `window_size`.

## Presentation

The card renders backend-provided evidence including:

- first retained outside-envelope observation;
- persistence-established timestamp when present;
- configured N-of-M criterion;
- policy ID and revision;
- upstream/downstream relationship states;
- policy/config provenance;
- topology provenance;
- backend claim boundary.

The component formats timestamps and human-readable labels only. It does not:

- count outside samples;
- evaluate N-of-M persistence;
- infer relationship relevance;
- infer topology;
- substitute a persistence result when the backend refuses.

## Bounded states

Backend refusal and uncertainty states remain visible rather than being converted into a generic healthy/degraded indicator.

Examples include:

- `REFUSED_POLICY_NOT_CONFIGURED`;
- `REFUSED_TRUNCATED`;
- `REFUSED_CONTEXT_AMBIGUOUS`;
- `REFUSED_TARGET_NOT_PRESENT`;
- `UNAVAILABLE`;
- `PERSISTENCE_NOT_ESTABLISHED`;
- `INSUFFICIENT_EVIDENCE`;
- `EVIDENCE_CONFLICT`.

A selector refusal can still show the resolved configured policy because policy resolution may succeed before evidence admission fails.

## Historical-policy limitation

The card surfaces the backend's current policy-application semantics instead of hiding them:

```text
CURRENT_CONFIG_APPLIED_TO_SELECTED_HISTORY
historical_policy_equivalence = UNVERIFIED
```

This means the UI may show the exact current configured policy used to evaluate selected historical evidence, but it does not state that the same policy revision was in force when the historical measurements were created.

## Technician workflow position

The Operator View now keeps three different evidence questions separate:

```text
Shared episode timeline
  What was retained, and when?

Sustained deviation
  When did this relationship satisfy its configured persistence criterion,
  and what related relationships were doing in that bounded window?

Reference ↔ selected comparison
  What changed between two explicitly selected functional-temporal cycles?
```

None of these views independently establishes physical root cause.

## Authority boundary

The presentation does not:

- upgrade anomaly to fault;
- claim causation;
- claim historical configured-policy equivalence;
- infer verified physical state;
- recommend or authorize equipment changes;
- call CADGrounded;
- bypass OEM, safety, engineering, or qualified human judgment.
