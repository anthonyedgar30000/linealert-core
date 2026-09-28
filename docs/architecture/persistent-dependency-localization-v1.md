# Persistent dependency localization v1

This increment adds deterministic multi-cycle localization over already-admitted condition-history samples.

It answers two bounded questions:

1. When did a target relationship first satisfy a declared persistence rule?
2. During that qualifying window, what evidence existed on topologically related upstream and downstream relationships?

It does not diagnose a physical root cause.

## Persistence semantics

V1 uses an explicit N-of-M rule:

```text
required_outside = N
window_size = M
```

Samples are processed in chronological order.

A target persistence onset is established only when the earliest complete M-sample window contains at least N quality-qualified outside-envelope samples.

The timestamp meanings are deliberately distinct:

- `first_outside_at` = first retained quality-qualified target sample outside the envelope anywhere in the selected history;
- `candidate_start_at` = first outside sample inside the earliest qualifying persistence window;
- `persistence_established_at` = timestamp of the final sample in that earliest qualifying window.

Therefore:

```text
first outside sample != degradation onset proven
persistence established != physical fault began then
```

The localizer reports when the evidence becomes sufficient to satisfy the declared N-of-M rule, not when a physical degradation process actually began.

## Sample admission

For persistence purposes:

- quality `good` + numeric value inside envelope + retained status `within` -> `WITHIN`;
- quality `good` + numeric value outside envelope + retained status `early` or `late` -> `OUTSIDE`;
- non-good quality or unknown status -> `UNRESOLVED`;
- numeric envelope state that contradicts retained temporal-rule status -> `CONFLICT`.

A target conflict prevents persistence localization.

If unresolved samples could change whether the N-of-M rule is satisfied, the result is `INSUFFICIENT_EVIDENCE`, not a negative finding.

## Relationship identity

One relationship history must preserve the same:

- asset ID;
- relationship ID;
- signal identity;
- engineering unit;
- min/max envelope;
- topology from/to endpoints.

Incompatible relationship/envelope metadata is refused rather than combined.

## Dependency window

Once persistence is established, the dependency analysis window is exactly the earliest qualifying target window.

When persistence is not established, the selected target history span is retained as the bounded analysis window but the result remains explicitly non-persistent or insufficient.

Topology is taken from the declared deterministic `TopologyGraph`.

Related relationship observations are classified as:

- `WITHIN_ENVELOPE`
- `INTERMITTENT_OUTSIDE`
- `PERSISTENT_OUTSIDE`
- `UNRESOLVED`
- `CONFLICT`
- `NO_EVIDENCE`

The same declared N-of-M rule is used when labeling a related relationship `PERSISTENT_OUTSIDE`.

A relationship known elsewhere in the supplied history but absent from the target analysis window is retained as `NO_EVIDENCE`; it does not silently disappear.

## Shared-upstream branches

A relationship whose downstream endpoint feeds the target's upstream node is classified as upstream dependency evidence.

For example:

```text
AlignmentConfirmed ─┐
                    ├─> LabelFeedCommand -> LabelAtPeelPoint
WebTensionStable ───┘
```

Both incoming branches can be summarized in the same target persistence window.

This can show patterns such as:

```text
target label presentation: PERSISTENT_OUTSIDE
alignment -> feed:          WITHIN_ENVELOPE
web-ready -> feed:          INTERMITTENT_OUTSIDE
initial contact:            PERSISTENT_OUTSIDE
```

That is dependency localization, not a causal proof.

## Historian selection boundary

`condition_history_sample_from_dict` remains available for reconstructing the retained historian condition shape without upgrading its meaning.

A separate read-only condition-history selector now provides typed, bounded historian records for this localizer. It refuses the localization handoff when the selected history is truncated, empty, spans multiple operating contexts, or was filtered to one relationship in a way that would hide dependency evidence.

The localizer itself still does not query TimescaleDB. This separation keeps evidence selection and persistence completeness outside the reasoning primitive while guaranteeing that a historian-backed caller cannot silently claim an earliest persistent onset from a clipped history.

## Evidence package

`dependency_localization_to_dict` emits:

- schema version;
- target relationship and topology;
- persistence rule;
- first outside timestamp;
- qualifying onset window;
- exact observation/cycle IDs used by the window;
- upstream/downstream relationship states;
- reasons and retained claim boundary.

The serializer does not recompute or reinterpret the result.

## Authority boundary

Persistent dependency localization does not establish:

- physical root cause;
- causation between related relationships;
- the true physical start time of degradation;
- verified physical component state;
- maintenance authority;
- engineering acceptance;
- safety approval;
- permission to alter equipment.

It is a deterministic localization of retained operational evidence for governed troubleshooting review.
