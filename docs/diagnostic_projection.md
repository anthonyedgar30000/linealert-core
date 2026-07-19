# Diagnostic Projection Engine

The Diagnostic Projection Engine is the symptom-first, reverse-facing view of the same process graph used by LineAlert Core.

It combines four explicitly supplied inputs:

1. an approved machine profile and process topology;
2. a versioned troubleshooting guide authored as governed expert knowledge;
3. an operator report preserving the reported timeline, observations, operating mode, and recent changes;
4. deterministic timing findings from replayed or live machine events.

It does not infer when degradation began from one cycle, declare a root cause, or approve a new normal.

## Labeler demo

Run the full diagnostic demo with:

```bash
linealert-diagnose \
  --config examples/labeler_demo_config.json \
  --input examples/labeler_demo_events.jsonl \
  --guide examples/labeler_diagnostic_guide.json \
  --operator-report examples/labeler_operator_report.json \
  --output labeler-diagnostic-report.json
```

The sample operator reports drifting label placement beginning around 13:40 during the approved 500 ml round-bottle mode. The supplied event stream contains one late timing relationship:

```text
LabelFeedCommand -> LabelAtPeelPoint
observed: 0.55 s
approved: 0.05-0.35 s
```

The projection therefore ranks the guide-authored label-presentation and web-path checks first. Bottle spacing, alignment, contact, wipe-down, inspection, and release relationships remain visible as healthy supplied evidence and can deprioritize unrelated checks without removing them.

## Check dispositions

- `evidence_aligned`: at least one relationship declared by the guide check is abnormal in the supplied findings;
- `guide_only`: the guide recommends the check, but the supplied timing evidence does not directly assess it;
- `deprioritized_by_healthy_evidence`: all supplied relationships declared by the check remain within their timing envelopes.

These dispositions rank investigation paths. They are not causal-confidence scores.

## Current boundary

This first implementation projects one supplied set of timing findings. A later time-series increment can add rolling trends, variability, change-point detection, and matched healthy-window comparisons while preserving the operator-reported timeline separately from machine-derived timing evidence.
