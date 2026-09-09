# Deterministic synthetic scenario v1

## Purpose

This increment gives the Plant Canvas a realistic but explicitly synthetic evidence story without connecting LineAlert to physical equipment.

The scenario is `labeler-roll-change-stability-v1` and is defined in `profiles/synthetic-labeler-roll-change-stability-v1.json`.

The goal is not to generate random numbers. The goal is to emit coordinated source observations that preserve a believable process relationship across a baseline window, a concern window, and a bounded verification run.

## Source model

The synthetic scenario exposes four source identities:

- `synthetic-mes/packaging-line-1`
- `synthetic-telemetry/labeler2`
- `synthetic-camera/labeler2`
- `synthetic-quality/labeler2`

The sources share a deterministic scenario timeline but remain semantically distinct. A camera classification is not treated as telemetry, a quality count is not treated as a physical-state measurement, and a derived comparison is not treated as causal proof.

## Coordinated story

The fixture has three windows:

1. **Synthetic baseline reference** — line speed 78 containers/min, presentation-interval standard deviation 7.8 ms, 5/5 containers inside the demo visual alignment envelope, and no apparent reject candidates.
2. **Synthetic concern window** — line speed remains 78 containers/min while presentation variability rises to 21.6 ms, the camera classifies 3/5 containers inside the demo alignment envelope, and two apparent reject candidates are present.
3. **Synthetic bounded verification run** — line speed remains 78 containers/min, presentation variability is 18.9 ms, 4/5 containers are classified inside the demo alignment envelope, and one apparent reject candidate remains.

The deterministic comparison therefore says only that the verification run is worse than the synthetic baseline and slightly better than the immediately preceding concern window while line speed is unchanged.

## Bounded finding

The demo may state:

> Alignment inconsistency persists while presentation-interval variability remains elevated relative to the synthetic baseline.

It may also say that this supports continued attention to presentation stability.

It must not state that presentation variability caused the visual skew, that a specific component is faulty, or that any setting change is safe or authorized.

## Numeric-value boundary

Every numeric value in this fixture is a synthetic scenario parameter chosen for internal consistency and demo readability.

These values are **not**:

- Speedway Packaging Machinery specifications;
- OEM thresholds;
- commissioned operating envelopes;
- safe operating limits;
- production recommendations;
- measurements from a physical labeler.

The current repository does not contain commissioned Speedway machine documentation sufficient to make those claims.

## Runtime boundary

The public demo still uses a browser control to represent receipt of coordinated source events. That control does not execute or authorize a machine run.

No live camera, PLC/controller, historian, MES, quality system, CMMS, dispatch, safety-control, or equipment-control connection is added by this increment.

Synthetic source event != physical observation.

Coordinated evidence != causation.

Improved trial != root-cause proof.

Successful trial != safe production change.
