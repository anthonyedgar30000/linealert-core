# Commissioned-vs-selected-time comparison v1

This increment adds a deterministic comparison layer over explicit functional-temporal historian selections.

The comparator does not decide that any record set is commissioned truth. The caller must explicitly supply the reference selection and the selected historical/current selection.

## Comparison flow

```text
explicit reference records
        +
explicit selected-time records
        ->
exact operating-context compatibility
        ->
semantic identity matching
        ->
state / coverage / transition comparison
        +
retained source metric deltas
        ->
bounded comparison result
```

## Exact context compatibility

V1 requires the reference and selected evidence to share the same:

- asset ID
- machine profile
- operating mode
- configuration version
- firmware version
- calibration ID
- sampling profile
- recipe ID
- product ID
- context tags

Component ID is not part of the global context because different phase/guard records may legitimately belong to different components. Component identity is part of each semantic comparison identity instead.

A mismatch refuses the comparison. The comparator does not silently normalize, substitute, or downgrade configuration differences.

## Reference ambiguity

The reference side must contain exactly one record for each semantic identity.

This is intentional. Multiple commissioned/reference observations for the same guard, invariant, phase, or transition require a later explicit baseline-selection or aggregation policy. V1 does not average repeated reference evidence or choose one implicitly.

The selected side may contain a chronological sequence for the same semantic identity. The latest record is compared to the reference, and the earliest current selected record that diverges is reported as `first_divergence_at`.

## Semantic identity

Like is compared only with like. Identity includes:

- record kind
- component ID
- phase ID
- requirement ID
- transition ID
- from/to phase IDs
- record semantic such as `transition_guard`, `phase_admission`, or `phase_assessment`

Missing or newly appearing semantic identities are retained as unresolved comparison points rather than paired approximately.

## Evidence validity

A state/value comparison requires `CURRENT` evidence on both sides.

Stale or unknown evidence is reported as unresolved. If no current semantic identity can be compared, the overall comparison is refused as insufficient evidence.

Historical evidence remains preserved; refusal means only that the selected records cannot support the requested current comparison.

## Numeric relationship deltas

Clock-qualified timing source bindings now retain their measured value, unit, declared min/max envelope, temporal-rule status, quality, semantic, and scope in immutable source provenance.

When a guard or invariant historian record preserves matching numeric source provenance on both sides, the comparator reports an exact selected-minus-reference delta.

Example:

```text
reference: 240 ms, VERIFIED, within envelope
selected:  550 ms, VIOLATED, late

delta: +310 ms
first divergence: selected record timestamp
```

A numeric difference is descriptive operational evidence. It is not automatically a fault, root cause, unsafe condition, or authorized maintenance action.

## Current scope

V1 compares explicit `FunctionalTemporalHistoryRecord` selections. It does not yet add a new historian HTTP time-range query surface or automatically choose the commissioned reference window.

That separation is deliberate: reference selection policy is an authority decision and should not be hidden inside the comparator.

A later read-only historian integration can select exact windows/cycles and feed them to this comparator without changing comparison semantics.

## Authority boundary

The comparator does not:

- infer which historical interval should be treated as commissioned truth;
- average or statistically synthesize a reference baseline;
- compare incompatible operating contexts;
- use stale evidence as current proof;
- convert temporal deviation into mechanical diagnosis;
- infer physical root cause;
- authorize equipment changes;
- call CADGrounded;
- grant maintenance, engineering, production, or safety approval.

It reports bounded differences in retained LineAlert evidence and preserves uncertainty.
