# Live shift clock and simulated telemetry

This demo increment adds time as a first-class operational dimension on the Plant Canvas.

## Synthetic operating clock

The public demo uses a deterministic accelerated 24-hour plant clock. The current demo ratio is **1 real second = 2 simulated minutes**. This is a visualization/testing parameter only; it is not derived from a plant clock, shift system, MES, scheduler, or historian.

The clock continues to advance while the line is:
- producing;
- stopped;
- in bounded diagnostic mode;
- executing a bounded diagnostic batch;
- returning to production verification.

## Scheduled windows

The demo overlays synthetic operating windows on the 24-hour ribbon, including production, changeover, maintenance availability, and sanitation. These are synthetic schedule fixtures rather than commissioned plant schedules.

LineAlert calculates a compact response view from the supplied schedule context:

```text
current simulated time
        +
next hard scheduled window
        +
response runway
        +
maintenance ETA
        |
        v
usable response slack
```

In this demo, usable slack is a simple deterministic scenario calculation. A real plant implementation would need commissioned definitions for shutdown/setup/restart time, production commitments, labor availability, safety constraints, maintenance windows, changeovers, and any process-specific restrictions.

**Schedule slack != authorization.** A displayed interval does not establish that an intervention is safe, permitted, feasible, or approved.

## Continuously moving plant evidence

When production is running, the synthetic plant emits continuously changing deterministic values for:
- line rates;
- processed counts;
- presentation variability;
- rolling quality;
- downstream buffer state.

The values use deterministic wave functions rather than random generation so the demo is reproducible and inspectable.

When production is stopped for diagnostics, production-rate signals transition to a stopped state rather than continuing to look like a running machine. The 24-hour plant clock still advances.

A bounded diagnostic run remains a separate evidence event. After repeated bounded improvement, production verification resumes the continuous production stream so diagnostic evidence and production-recovery evidence stay distinct.

## Boundaries

- simulation time != plant time
- telemetry != diagnosis
- anomaly != fault
- schedule slack != safe intervention window
- maintenance ETA != guaranteed availability
- scheduled window != authorization
- bounded trial response != causal proof
- LineAlert trial arm != HMI equipment execution
- successful bounded trial != verified production recovery
- synthetic stream != verified physical state
