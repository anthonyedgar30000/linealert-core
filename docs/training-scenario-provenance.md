# Training scenario provenance gate

LineAlert training scenarios are not arbitrary fault injections. A scenario becomes playable only when its failure pattern has a documented field basis and the simulator can preserve the distinction between the historical/source pattern and the evidence produced inside the current exercise.

This training route is separate from `/commissioning`. Commissioning fixtures remain synthetic engineering test inputs. They may exercise deterministic LineAlert paths, but they do not become training cases merely because they are convenient to inject.

## Admission states

- **Site-validated case** — derived from a documented plant incident or reviewed field case with enough evidence to reproduce the relevant mechanism and observations. Identifying plant details may be removed or generalized.
- **Field-documented pattern** — documented by an OEM, equipment manufacturer, qualified service source, or other credible industrial reference. It may be used as a teaching scenario, but it must not be presented as a specific plant incident.
- **Composite** — combines multiple admitted field sources. Each contributing mechanism must remain traceable and the UI must say that the scenario is composite.
- **Research required** — plausible or useful as a test idea, but missing adequate field provenance. This state is locked and not playable in the training route.

A source does not prove that the same root cause exists on another machine. Historical pattern != current root cause.

## Minimum case record

Every playable case should preserve:

1. case identifier and admission state;
2. source identity and source type;
3. equipment/process scope;
4. documented symptom or failure pattern;
5. which observations are source-backed versus simulator-generated teaching observations;
6. persona visibility and authority boundaries;
7. allowed interventions and escalation boundaries;
8. expected verification after an intervention;
9. assumptions, simplifications, and known unknowns;
10. reviewer or validation status when plant/OEM review is available.

If the simulator needs a gauge, sensor, controller tag, threshold, timing value, or physical observation that the source does not establish, it must be marked as a training assumption or omitted. The UI must not silently invent plant instrumentation.

## First admitted pattern: LA-T01

**Title:** Label web tension inconsistency

**Admission:** Field-documented pattern; not a site-validated incident.

**Equipment scope:** Pressure-sensitive label application / label web handling.

**Documented basis:**

- Pack Leader USA's troubleshooting guidance associates repeated applicator jams at the same point in the cycle with inconsistent label-web tension and describes loose or overtightened web as a feed-disruption mechanism: https://www.packleaderusa.com/blog/how-to-diagnose-misapplied-pharma-labels-in-2026
- Videojet describes label-web tension, alignment, movement, web breaks, and misapplied labels as operating concerns addressed by its 9310 label applicator controls: https://www.videojet.com/us/homepage/products/labelers/videojet-9310.html

**Simulator boundary:** The training case may reproduce the documented relationship between recurring jams and web-tension instability. It must not invent a numeric web-tension sensor, OEM threshold, PLC tag, or authorized adjustment procedure unless a later source establishes it.

**Training pacing boundary:** LA-T01 uses deterministic scenario times for the browser exercise so pause, normal speed, fast-forward, and skip-to-next-event controls have real behavior. Those timestamps are simulator-generated pedagogical pacing only. They are not manufacturer cycle times, commissioned timing limits, sampled telemetry, or evidence that a real machine would fail on the same schedule. The source-backed relationship is recurrence at the same cycle point, not the exercise's wall-clock spacing between events.

**Learning objective:** Establish a baseline, notice recurrence, collect evidence without jumping directly from symptom to root cause, use only evidence available to the current persona, escalate when authority or instrumentation ends, and verify the same original condition after an authorized intervention.

## Verification and supersession

When a plant, OEM manual, technician review, or lab test provides better evidence, update the case record rather than silently replacing the older basis. Retain the prior source and note what was superseded. A successful simulator run validates the exercise path; it does not validate a production diagnosis or authorize a production change.
