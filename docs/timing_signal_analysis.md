# Timing Signal Analysis

The timing signal-analysis layer examines repeated `TimingFinding` observations for the same approved relationship. It is deliberately deterministic and policy-driven.

It can distinguish:

- insufficient history;
- stable behavior;
- one isolated excursion;
- recurring excursions;
- rising variability;
- gradual drift;
- a sustained shift outside the approved timing envelope.

The analyzer also produces a candidate statistical change boundary and compares it with the operator-reported symptom start. That boundary is not treated as the proven beginning of degradation.

## Historical labeler demo

```bash
linealert-diagnose \
  --config examples/labeler_demo_config.json \
  --input examples/labeler_timing_history.jsonl \
  --guide examples/labeler_diagnostic_guide.json \
  --operator-report examples/labeler_operator_report.json \
  --signal-policy examples/labeler_signal_policy.json \
  --output labeler-history-report.json
```

The demo supplies 18 label-presentation cycles. The early observations remain near 0.20 seconds, the relationship becomes more variable, then drifts upward, and the final observations remain above the approved 0.05–0.35 second envelope.

The expected detected patterns are:

```text
recurring_excursions
rising_variability
gradual_drift
sustained_shift
```

The candidate statistical change boundary appears before the operator-reported symptom time. The report preserves both timestamps separately rather than replacing the operator's account or claiming an exact failure start.

## Governed thresholds

All analysis thresholds are loaded from an explicit JSON policy. They include baseline and recent window sizes, minimum history, sustained-excursion count, variability ratio, drift magnitude, directional consistency, and change-point segment requirements.

These are reviewable operating assumptions, not hidden model weights. Changes should follow the normal branch, test, review, version, and rollback workflow.

## Current boundary

This increment analyzes event-to-event timing histories. It does not yet process high-rate vibration, motor-current spectra, audio, images, or continuous analog waveforms. Those require sampling-quality metadata, filtering rules, aliasing controls, and domain-specific analysis.
