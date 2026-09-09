# Canvas-owned troubleshooting

LineAlert's primary operational surface is the plant model. Troubleshooting is attached to the affected asset instead of sending the operator into a separate diagnostic application.

## Runtime surface

For an asset with an active concern, the Plant Canvas owns the visible loop:

```text
asset selected on plant model
        |
        v
current concern + run mode
        |
        v
current evidence + historical context
        |
        v
ranked bounded actions
        |
        v
human selects one commissioned action
        |
        v
LineAlert arms bounded evidence window
        |
        v
operator executes from HMI
        |
        v
new evidence is assembled
        |
        v
human confirms / corrects / escalates
        |
        v
rerank on the same asset
        |
        +----> repeat or production verification
```

The operator should not need to navigate into historian, CMMS, diagnostic-projection, or episode-timeline screens to understand the next bounded move. Those systems remain evidence sources underneath the asset workspace.

## Canvas semantics

The plant model answers **where the operational concern lives and what dependencies surround it**.

The selected asset workspace answers:

- what happened;
- current run mode;
- what evidence matters now;
- what the best-supported next bounded move is;
- what action was selected;
- what the latest bounded trial showed;
- how the ranking changed;
- whether production verification is now appropriate.

Stable assets remain quiet. An active asset can carry its concern, current evidence, ranked actions, trial state, and decision history without turning the entire plant canvas into a diagnostic dashboard.

## Evidence ownership

Machine/sensor history, CMMS history, operator observations, current telemetry, camera classifications, quality evidence, and topology remain distinct evidence inputs. The canvas does not collapse them into root-cause truth.

The diagnostic/historian engine therefore remains an evidence engine underneath the simple workflow. Historical evidence may support, contradict, or deprioritize a candidate path without proving current physical state or current root cause.

## Trial ownership

LineAlert may arm and record a bounded trial definition, selected action, expected evidence window, and review state. Equipment execution remains at the machine/HMI under commissioned plant authority.

The five-container trial in the synthetic Labeler 2 demonstration is a scenario-specific trial definition, not a platform constant.

## Boundaries

- telemetry != diagnosis
- anomaly != fault
- topology relationship != causation
- historical pattern != current root cause
- recommendation != authorized action
- LineAlert trial arm != equipment execution
- successful bounded trial != safe production change
- production recovery requires separate production-condition evidence

The current public demo is synthetic. Its topology, numeric values, action authority, trial size, and deterministic outcomes are demo parameters, not OEM guidance or commissioned plant truth.
