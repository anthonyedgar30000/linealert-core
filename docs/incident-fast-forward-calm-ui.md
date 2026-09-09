# Incident fast-forward and calm workspace

This static demo increment keeps the synthetic plant moving while reducing operator-facing information density.

## Demo-time control

`Speed up to incident` accelerates the deterministic simulation from the current pre-incident state to six simulated minutes before the commissioned synthetic incident threshold. During acceleration the same clock, counts, buffers, rates, and presentation signal continue advancing. The control does not teleport a single signal or represent plant control. At the pre-incident point the demo returns to normal speed so the viewer can observe the concern threshold being crossed.

## Progressive disclosure

Stable assets remain quiet. Once Labeler 2 crosses the synthetic concern threshold, its workspace emphasizes the best-supported next bounded move plus usable slack, maintenance ETA, and the next hard window. Detailed evidence, history/rationale, alternate allowed actions, and decision history remain available through disclosure sections.

## Boundaries

- simulation time != plant time
- telemetry != diagnosis
- historical pattern != current root cause
- schedule slack != authorization
- recommendation != authorized action
- LineAlert demo controls != equipment commands
- successful bounded trial != verified production recovery

All times, thresholds, schedule windows, telemetry values, action authority, trial size, and outcomes in this demo are synthetic deterministic parameters and are not OEM limits or commissioned plant truth.
