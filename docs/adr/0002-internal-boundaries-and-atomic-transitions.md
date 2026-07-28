# ADR-0002: Internal boundaries and atomic deterministic transitions

## Status

Proposed in a draft-only documentation pull request.

This ADR is not accepted, merge-authorized, or implementation authority while Issue #15 remains
open and the `main` independent-review control is unverified. It refines ADR-0001; it does not
replace the repository boundary established there.

## Context

`linealert-core` is currently one private repository and one installable Python package. It has no
recorded production deployment, physical-equipment connection, network listener, persistence
integration, or equipment-control path.

The package now contains several distinct kinds of responsibility:

- immutable machine, topology, baseline, rule, finding, and evidence types;
- deterministic applicability, temporal, topology, envelope, signal, and diagnostic reasoning;
- Fusion Mosaic in-process subscription delivery and event-identity handling;
- replay, streaming admission, file loading, reporting, and command-line adapters;
- verification tests and supplied labeler-demo fixtures.

Keeping these responsibilities in one repository does not require treating them as one
undifferentiated module. Likewise, drawing internal package boundaries does not justify a service
split or a separate contracts repository.

The current event path is stateful. Fusion Mosaic retains event fingerprints, `TimingMonitor`
retains unmatched starts, and `StreamConsumer` retains source sessions and sequence positions.
The correct deterministic model is therefore a state transition:

```text
(previous_state, event, immutable_configuration)
    ->
(new_state, outputs, transition_evidence)
```

It is not merely:

```text
event -> finding
```

Current inspection also identifies a transaction-boundary risk inside core ingestion:

- Fusion Mosaic records a new event fingerprint before all subscribed handlers complete;
- a timing end event removes its stored start before validating that the resulting delay is valid;
- earlier subscribers may mutate state before a later subscriber raises;
- diagnostic derivation occurs after Mosaic delivery has already mutated its state.

These observations identify possible failure windows. They are not evidence of an operational
incident, physical-machine failure, unsafe condition, or deployed-system defect.

## Decision

### 1. Keep one authoritative repository and one deployable package for now

Do not create a separate analysis service, contracts repository, or independently deployed
reasoning service without observed evidence that a package boundary is insufficient.

The initial target is enforceable internal architecture within `linealert-core`.

### 2. Establish five internal responsibility boundaries

```text
contracts
    Immutable types and canonical representations for events, identity,
    configuration, topology, rules, baselines, findings, uncertainty,
    transition evidence, and replay manifests.

kernel
    Applicability validation, temporal reasoning, topology reasoning,
    expected-versus-observed assessment, signal analysis, and bounded
    diagnostic derivation.

orchestration
    Fusion Mosaic subscription declaration, deterministic ordering,
    atomic event-transition coordination, deduplication, and delivery receipts.

adapters
    Streaming admission, replay files, JSON/CSV loading, report serialization,
    command-line interfaces, simulators, and future external connectors.

verification
    Unit tests, transition-atomicity tests, contract-conformance tests,
    canonical replay corpus, output digests, and independent comparison tools.
```

These are logical boundaries first. They may initially remain namespaces inside the same Python
package. Moving files is not the first step and is not required to accept the boundary.

### 3. Enforce one-way dependency direction

The intended dependency direction is:

```text
adapters -> orchestration -> kernel -> contracts
verification -> adapters/orchestration/kernel/contracts
contracts -> Python standard library only
```

Permitted exceptions must be explicit and justified. In particular:

- the kernel must not depend on transport sessions, files, CLI state, or network clients;
- contracts must not import reasoning, orchestration, or adapters;
- adapters may resolve which immutable configuration version to supply, but the kernel must not
  resolve `latest`, `current`, or wall-clock-dependent configuration itself;
- external governance workflows may produce approved baseline or rule evidence, but the kernel
  only validates and consumes the resulting immutable records.

### 4. Treat ingestion as an atomic deterministic transition

For one admitted event, the orchestration boundary must provide all-or-nothing state semantics:

```text
validate -> prepare transition -> derive outputs -> commit state and receipt
```

If any step raises or rejects the event:

- the event-identity ledger must not mark the event as successfully consumed;
- unmatched temporal-start state must remain exactly as it was before the attempt;
- no subscriber may retain a partial mutation;
- retrying the same valid event must not be suppressed as a duplicate solely because a prior
  attempt failed;
- no successful receipt may be emitted;
- failure evidence may be recorded separately without pretending the transition committed.

The implementation may use pure transition functions, prepared state deltas, copy-on-write state,
transaction objects, or bounded snapshot-and-rollback. The selected mechanism must be simpler than
the behavior it verifies and independently testable.

### 5. Make deterministic state and version identity explicit

Future transition and replay evidence should be sufficient to identify:

- event schema version;
- event fingerprint algorithm and version;
- exact event fingerprint;
- asserted source, asset, and component identity;
- identity-validation or resolution evidence when such a process actually occurred;
- source timestamp, receive timestamp where applicable, and clock quality;
- engineering unit, quality, calibration identity, and applied transform evidence;
- machine-profile, topology, configuration, firmware, sampling-profile, rule-set, baseline, and
  comparison-policy versions or immutable digests as applicable;
- kernel build identity;
- prior-state checkpoint or digest;
- resulting-state checkpoint or digest;
- output schema versions and output digest.

No field should imply that asserted source data is verified physical truth.

### 6. Preserve authority boundaries structurally

The architecture must continue to preserve:

```text
telemetry != diagnosis
anomaly != fault
correlation != causation
model_match != proof
recommendation != authorized_action
historical_pattern != current_root_cause
sensor_value != verified_physical_state
successful_test != safe_production_change
```

Baseline approval, rule promotion, production release, safety approval, trade sign-off, and
equipment-control authorization remain external governed decisions. Core types may preserve their
evidence; core computation does not create the authority.

### 7. Service extraction requires observed evidence

A separately deployed service is considered only when package boundaries no longer address an
observed need, such as:

- documented release blocking between independently changing responsibilities;
- measured and materially different scaling or isolation requirements;
- a credible incident that process isolation would have contained but a package boundary would
  not;
- separate operating teams and on-call ownership already exist;
- an independently certifiable reasoning boundary is required;
- version compatibility, review enforcement, deployment verification, rollback, and operational
  observability are functioning across the proposed boundary.

Repository count and architectural fashion are not extraction criteria.

## Staged implementation plan

### Stage 0 — inventory and decision evidence

Document current dependencies, mutable state, transaction points, failure windows, test coverage,
and unresolved questions. No runtime behavior changes.

Rollback: close the draft without merge.

### Stage 1 — characterize current behavior with tests

Add focused tests proving the current success behavior and exposing partial-state failure windows.
Tests must cover handler failure, invalid negative timing, multiple subscribers, diagnostic failure,
and retry after failed ingestion.

Rollback: revert test-only commits. No runtime change.

### Stage 2 — make core transitions atomic

Introduce the smallest mechanism that makes event admission, temporal state, subscriber outputs,
and event receipts commit together or not at all. Preserve public behavior for successful inputs.

Rollback: revert to the prior implementation and retain the failing characterization tests as
known-risk evidence only if explicitly approved.

### Stage 3 — enforce internal dependency direction

Create or refine internal namespaces and add import/dependency checks. Avoid simultaneous logic
rewrites and broad file movement.

Rollback: disable the dependency rule and revert namespace moves without altering runtime behavior.

### Stage 4 — add versioned transition and replay manifests

Add explicit schema/build/configuration/state identities and a canonical golden replay corpus.
A green replay proves deterministic equivalence for the represented corpus; it does not authorize
production use.

Rollback: retain the previous manifest version and pin consumers to the last known-good contract.

### Stage 5 — reconsider external packaging or services

Only evaluate a separate package, repository, or service after the extraction criteria are met by
recorded evidence.

Rollback must be designed before extraction and include last-known-good version pinning and a
single-package deployment path.

## Consequences

### Positive

- Internal cohesion is defined by responsibility rather than repository count.
- Transport admission cannot silently become reasoning authority.
- Stateful determinism becomes explicit and testable.
- Replay evidence can distinguish changed inputs from changed behavior.
- Future service extraction remains possible without paying its operational cost now.

### Negative

- Atomic state transitions require additional design and tests.
- Explicit versions and state digests add contract surface.
- Dependency enforcement may reveal existing cycles and require incremental cleanup.
- A single package still shares one release cadence until evidence justifies changing it.

### Risks

- A drawn boundary without CI enforcement may erode.
- Version fields without canonicalization may create false reproducibility.
- Snapshot-and-rollback could become complex or expensive if state grows without bounds.
- A manifest may look complete while omitting an ambient input.
- Green tests may be misread as operational or safety approval.

## Non-decisions

This ADR does not:

- select a message broker, database, serialization framework, or network protocol;
- create an external connector or network listener;
- change baseline, diagnostic, signal, or timing thresholds;
- authorize equipment connection or control;
- approve a separate contracts repository or analysis service;
- claim current replay reports are complete reproducibility manifests;
- claim the review gate is functioning.

## Verification and acceptance gate

Acceptance requires:

1. independent review of the exact ADR head;
2. verified `main` review enforcement under Issue #15;
3. confirmation that the inventory matches current repository reality;
4. explicit approval of the staged plan before runtime changes begin.

Until then:

```text
adr_written != architecture_accepted
architecture_accepted != implementation_authorized
tests_green != transition_proven_for_all_inputs
transition_deterministic != safe_production_change
```
