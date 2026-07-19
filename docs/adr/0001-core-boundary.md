# ADR-0001: LineAlert Core boundary

## Status

Accepted for the initial implementation.

## Context

LineAlert needs real deterministic software beneath AI-assisted interpretation. The existing
`helix-protocol-kernel` defines governed evidence and transport contracts, while legacy
LineAlert repositories contain useful prototypes but mix demo assumptions with the future
product boundary.

## Decision

`linealert-core` owns:

- typed machine events;
- the Fusion Mosaic event fabric;
- deterministic event subscriptions and delivery receipts;
- correlation-aware temporal relationships;
- physical and logical process topology;
- expected-versus-observed evaluation;
- bounded diagnostic recommendations;
- later PMV and governed rule-pack promotion.

The Fusion Mosaic preserves event identity, source, time, topology, quality, and correlation.
It delivers each event only to consumers that explicitly declare a dependency on that event
type.

The core does not try to prove root cause. It reports observed relationships, compatible
process regions, contradictions, missing information, and low-risk next checks while retaining
uncertainty.

ML and LLM outputs will enter as typed derived observations. They may rank resemblance or
propose rule changes, but they do not rewrite live deterministic logic or authorize physical
actions.

Candidate rules and parameters will eventually move through validation, historical replay,
regression testing, shadow mode, approval, versioned activation, monitoring, and rollback.

## Consequences

- The first vertical slice is intentionally small and uses no AI service.
- Arbitrary weighted causal-confidence scoring from the demo repository is not carried forward.
- Integration with `helix-protocol-kernel` will occur at governed package boundaries rather
  than by merging the repositories.
- Legacy repositories remain design archaeology and test-fixture sources.
