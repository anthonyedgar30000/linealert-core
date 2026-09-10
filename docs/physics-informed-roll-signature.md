# Physics-informed synthetic roll signature v1

Status: controlled synthetic demo only.

This increment gives the Labeler 2 roll-change scenario a small deterministic physics kernel instead of independently invented telemetry channels. It is not a Speedway/OEM machine model and does not claim that a real labeler has these coefficients, resonances, geometry, sensor mounting, or failure behavior.

## Bounded physical relationships

The demo calculates rotational frequency from RPM (`f = RPM / 60`), angular velocity (`omega = 2*pi*f`), an idealized rotating-unbalance forcing term (`F = m*e*omega^2`), an approximate torque-to-web-tension relationship (`T = torque / roll radius`), and an approximate motor-current relationship (`I = torque / Kt`).

One hidden synthetic setup disturbance increases effective eccentricity and periodic tension modulation after a recorded roll change. Because the same tension modulation changes required torque, motor-current modulation moves with it. The unbalance forcing term changes the 1x rotational vibration channel. The resulting channels therefore share a deterministic physical dependency instead of being unrelated random graphs.

The conversion from unbalance force to vibration velocity uses an illustrative synthetic transfer gain. A real vibration response depends on structural mass, stiffness, damping, resonance, mounting, sensor orientation, bandwidth, and other machine-specific factors that are not commissioned in this repository.

## Healthy and problem episodes

A synthetic healthy changeover begins with a small transient and settles toward the configured reference. A synthetic problem episode develops a persistent coupled signature. LineAlert evaluates the problem episode against the healthy reference at the same elapsed time after production restart.

The v1 signature becomes distinguishable only when all configured conditions are true: vibration 1x amplitude is at least 1.5x the same-elapsed healthy reference, web-tension modulation is at least 0.65 N peak-to-peak, and motor-current modulation is at least 0.17 A peak-to-peak. The deterministic evaluator checks every 15 seconds.

That signature event is supporting evidence. It is not a diagnosis, proof that the roll change caused the later concern, or proof of physical state.

## Primary product use: investigation weighting

The physics signature is primarily a behind-the-scenes evidence layer, not a prime operator dashboard. The operator-facing view should not lead with RPM, vibration, tension and current calculations merely because LineAlert used them internally.

For the roll-change demo, a deterministic ordered sequence can promote the recorded roll change to a **STRONG investigation anchor**:

1. a label-roll change is recorded;
2. production restarts;
3. the coupled synthetic signal signature becomes distinguishable;
4. presentation variability deviates later;
5. the LineAlert concern threshold crosses.

When that sequence exists, LineAlert weights the recent changeover as the best place to begin investigation. This is investigation priority, not causal probability. The raw calculated values remain available under analyst/evidence drill-down and in the Event Log.

The operator-facing next move is deliberately mundane: **check roll loading and the web path against the approved changeover reference.** The demo prompts inspection of whether the roll is seated/centered, whether the web follows the approved thread path, whether guide/spacing matches the marked setup reference, and whether the web tracks without obvious drag or sideways pull. These are illustrative generic demo prompts only; a real deployment must replace them with client/OEM instructions and commissioned visual references. Observe first; correct only a confirmed mismatch under an authorized procedure.

## Demo chronology

For a calendar-seeded alignment incident, the Event Log can show a sequence such as:

- roll-change record completed
- production resumed
- coupled rotational/tension/current signature becomes distinguishable from the synthetic healthy settling reference
- presentation variability crosses its existing synthetic envelope
- LineAlert concern threshold crosses

The exact synthetic values and elapsed times vary deterministically by incident ID. Event order != causal proof.

## Commissioning path

A real deployment would replace or calibrate demo coefficients and thresholds from available OEM/equipment documentation, actual geometry and drive information, sensor identity and calibration, operating mode/SKU/speed, known-good runs, historical episodes, controlled tests where authorized, and qualified expert review. Only commissioned relationships should become authoritative operating evidence.

Canonical boundaries remain in force: model match != proof; investigation priority != causal probability; historical pattern != current root cause; sensor value != verified physical state; recommendation != authorized action; successful test != safe production change.
