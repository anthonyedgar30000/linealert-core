# Replay timing baseline assessment

LineAlert can optionally take timing findings produced during deterministic replay, resolve the exactly applicable commissioned baseline, and calculate drift without changing the existing timing rules or converting the result into a diagnosis.

```text
captured or simulated events
→ deterministic replay
→ correlated timing finding
→ explicit rule applicability context
→ governed baseline resolution
→ drift and approved-envelope assessment
→ machine-readable bounded evidence
```

## Required inputs

The replay command continues to require its normal rule/topology configuration and event file. Baseline assessment is enabled only when both additional inputs are supplied:

- a governed baseline registry;
- a timing-baseline context file.

```text
linealert-replay \
  --config examples/labeler_config.json \
  --input examples/labeler_events.jsonl \
  --baseline-registry examples/labeler_baseline_registry.json \
  --timing-baseline-contexts examples/labeler_timing_baseline_contexts.json
```

Supplying only one of the two baseline inputs is rejected. Baseline thresholds remain explicit command-line policy values:

```text
--baseline-sigma-threshold 3.0
--baseline-minimum-absolute-drift 0.02
```

## Explicit timing context

A timing finding supplies the measured delay, asset, correlation, timestamps, rule identity, and observation key. It does not by itself prove the operating mode, configuration, firmware, calibration, sampling profile, or product context.

The context file therefore binds a timing rule to explicit applicability evidence:

- component identity;
- operating mode;
- configuration version;
- firmware version;
- calibration identity;
- sampling profile;
- observation source and quality;
- exact context tags such as product, stock, speed, or load class.

LineAlert does not infer or silently fill these fields from a nearby baseline.

## First-class outcomes

Each timing finding produces one of three processing dispositions:

- `evaluated`: baseline resolution was attempted;
- `context_not_configured`: no explicit context existed for the rule;
- `comparison_rejected`: the observation could not be compared, for example because its quality or engineering unit was not permitted.

An evaluated finding can still resolve to:

- `resolved`;
- `not_found`;
- `ambiguous`.

No-match, ambiguity, rejected comparison, and missing context remain visible in the report rather than being discarded or replaced by a fallback selection.

## Separate comparisons

The replay output preserves two different comparisons:

```text
temporal-rule status != commissioned-baseline drift
temporal-rule envelope != approved baseline envelope
```

A delay can be inside the broad temporal rule while still drifting from its commissioned baseline, or outside the approved baseline envelope. The output retains both statuses so one does not silently overwrite the other.

## Authority boundary

```text
timing finding != diagnosis
baseline resolved != physical state verified
drift detected != fault
envelope excursion != root cause
persistent drift != approved new normal
replay result != authorized action
```

This increment reads files and produces replay evidence only. It does not connect to live telemetry, modify timing or diagnostic rules, re-baseline automatically, deploy software, or control equipment.
