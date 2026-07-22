# Governed baseline resolution

LineAlert resolves a commissioned baseline before calculating drift. Resolution is exact and deterministic; it does not silently choose a nearby recipe, firmware version, calibration, sampling profile, or machine configuration.

```text
current observation
→ validate source, timestamp, quality, unit, and operating context
→ resolve one applicable effective baseline
→ stop on no match or ambiguity
→ calculate distance from baseline
→ calculate approved-envelope status separately
→ emit a bounded assessment with retained uncertainty
```

## Applicability

A baseline applies only when all of the following match:

- asset and component identity;
- observation key;
- operating mode;
- configuration version;
- firmware version;
- calibration identity;
- sampling profile;
- exact context tags, such as recipe, product, stock, speed class, or load class.

A structurally valid baseline is not automatically applicable. `not_found` and `ambiguous` are first-class outcomes, and neither outcome permits drift calculation.

## Preserved evidence

Each baseline record preserves:

- baseline identity and version;
- source identity and exact source reference;
- captured time range and clock quality;
- engineering unit and sample count;
- test conditions;
- reviewer identity, approval time, and approval reference;
- configuration, firmware, calibration, sampling, and operating context.

Current observations preserve their own source, timestamp, quality, unit, and applicability context in the emitted assessment.

## Append-only lifecycle

A new baseline can name the prior baseline it replaces. The prior record remains present, searchable, and unchanged. Separate invalidation records can make a baseline ineligible without deleting it.

The registry rejects:

- unknown replacement targets;
- replacement cycles;
- multiple successors branching from one baseline;
- replacements that change applicability scope or engineering units;
- invalidations that reference unknown baselines.

An invalidated successor does not silently reactivate its predecessor. Restoration requires an explicit reviewed record.

## Baseline versus envelope

```text
baseline != approved operating envelope
```

The baseline represents commissioned expected behaviour. The envelope represents permitted behaviour. An observation can therefore be:

- within expected baseline behaviour;
- drifted from baseline while still inside the approved envelope;
- outside the approved envelope.

Thresholds are explicit policy values: a sigma multiplier, a minimum absolute drift, and the observation qualities permitted for comparison.

## Authority boundary

```text
baseline resolved != physical state verified
drift detected != fault
envelope excursion != root cause
persistent drift != approved new normal
comparison completed != authorized action
```

This increment does not connect to live telemetry, change diagnostic rules, re-baseline automatically, deploy software, or control equipment.
