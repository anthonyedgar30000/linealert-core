# Current dependency and transaction inventory

## Document status

Draft architecture evidence captured from repository `anthonyedgar30000/linealert-core`.

Baseline inspected:

```text
main commit: 6858d4a639c0dc27853c313e545d3af467ec1412
repository visibility: private
open pull requests before this workstream: none
Issue #15: open
independent-review enforcement: unverified
recorded deployment state: not_deployed
physical-equipment connection: no evidence
network listener: no evidence
equipment-control path: no evidence
```

This inventory is read-only architectural analysis. It does not establish that a possible failure
window has occurred in operation, that a sensor value is physically correct, or that any change is
safe for production.

## Available equipment context

The repository contains a supplied pressure-sensitive labeler demo, machine profile, process graph,
timing envelopes, simulated/captured-event examples, and related tests. Repository search during
this inventory did not surface OEM manuals, electrical drawings, pneumatic diagrams, safety
assessments, calibration certificates, controller backups, or physical commissioning records.

Consequently, this document makes no equipment-design, control, maintenance, or safety claim. Its
scope is software dependency and state-transition behavior only.

## Current responsibility map

### Contract-shaped modules

| Module | Current responsibility | Boundary observation |
| --- | --- | --- |
| `events.py` | Immutable `MachineEvent`, quality, canonical payload, SHA-256 fingerprint | Contract-shaped, but schema and fingerprint algorithm are not separately versioned. Event attributes are shallowly frozen. |
| `machine.py` | Machine profile, components, dependencies, event bindings, applicability validation | Contains immutable configuration and validation behavior; a future split should keep data types from depending on adapters. |
| `topology.py` | Dependency graph and topology context | Kernel configuration plus deterministic query behavior. |
| `timing.py` | Temporal rules, timing findings, statuses, and stateful event pairing | Mixes contract types with mutable transition behavior. |
| `baseline.py` | Baseline applicability, evidence, records, invalidations, resolution, and drift assessment | Mixes immutable governed records with deterministic resolution/comparison. It does not perform the external human approval workflow. |
| `diagnostics.py` | Diagnostic recommendation type and deterministic derivation | Mixes output contract and pure derivation behavior. |
| `signal_processing.py` | Versioned signal-analysis policy, assessment types, and deterministic series analysis | Primarily a pure kernel function over supplied findings and policy. |
| `diagnostic_projection.py` | Operator report, diagnostic guide/projection types and projection behavior | Requires separate inspection before any physical package move; conceptually spans contracts and kernel. |

### Kernel-shaped modules

| Module or class | Current responsibility | State model |
| --- | --- | --- |
| `MachineProfile.validate_event()` | Validate asserted asset/component/event applicability | No retained transition state observed. |
| `TimingMonitor` | Correlate start/end events and compare delay with approved rule envelope | Retains unmatched starts in `_starts`. |
| `TopologyGraph` | Resolve deterministic topology context | Configuration object; no per-event mutation observed in inspected path. |
| `DiagnosticEngine` | Convert timing deviation into bounded next checks | Holds topology reference; recommendation path is otherwise derived from supplied finding. |
| `TimingSignalAnalyzer` | Analyze supplied timing histories under explicit policy | No retained analysis history; groups and analyzes each supplied tuple. |
| `BaselineRegistry` | Resolve effective immutable baselines and compare observations | Builds indexes/effective records during construction; evaluation is read-oriented after initialization. |
| `DiagnosticProjectionEngine` | Build symptom-first projections from supplied report/findings/configuration | Requires focused transaction and dependency inspection before implementation planning. |

### Orchestration-shaped modules

| Module or class | Current responsibility | Boundary observation |
| --- | --- | --- |
| `mosaic.py` / `FusionMosaic` | Subscription declaration, deterministic registration order, event-id collision detection, deduplication, handler invocation, delivery receipt | In-process orchestration, not external transport. It currently owns a mutable successful-event ledger and invokes stateful consumers directly. |
| `pipeline.py` / `LineAlertCore` | Construct component graph, validate event, publish through Mosaic, select timing findings, derive recommendations | Composition root and current transaction coordinator, but it does not provide all-or-nothing rollback across component state. |

### Adapter-shaped modules

| Module | Current responsibility | Boundary observation |
| --- | --- | --- |
| `streaming.py` | Admit bounded source sessions and sequence-valid envelopes, preserve transport evidence, call `LineAlertCore.ingest()` | Correctly treats transport evidence as distinct from event meaning. After PR #20, new-session state is committed only after core ingestion succeeds. |
| `replay.py` | Load JSONL/CSV events and JSON configuration, construct core, replay ordered events, serialize report | Already a caller of the core rather than a reasoning implementation. Report is not yet a complete versioned state-transition manifest. |
| `baseline_io.py` | Load baseline records/invalidations and serialize evaluations | File adapter around baseline contracts and kernel behavior. |
| `signal_io.py` | Load signal-analysis inputs/policies and serialize outputs | File/report adapter; confirm exact imports before dependency enforcement. |
| `diagnostic_io.py` | Load diagnostic profile/guide/report evidence | File adapter; confirm exact imports before dependency enforcement. |
| `cli.py`, `diagnostic_cli.py` | Command-line composition | Adapter boundary. |
| `simulator.py` | Produce bounded supplied-event demo data | Test/demo adapter, not verified equipment telemetry. |

## Observed dependency paths

The inspected source establishes these direct paths:

```text
pipeline.py
  -> diagnostic_projection.py
  -> diagnostics.py
  -> events.py
  -> machine.py
  -> mosaic.py
  -> timing.py
  -> topology.py

mosaic.py
  -> events.py

timing.py
  -> events.py

diagnostics.py
  -> timing.py
  -> topology.py

streaming.py
  -> events.py
  -> machine.py
  -> pipeline.py
  -> topology.py

replay.py
  -> events.py
  -> machine.py
  -> pipeline.py
  -> timing.py
  -> topology.py

baseline_io.py
  -> baseline.py

signal_processing.py
  -> timing.py
```

The existing graph is small enough to refactor incrementally. It does not justify a new deployed
service.

## Mutable state inventory

### `FusionMosaic`

Current mutable members:

```text
_subscriptions
_subscription_names
_fingerprints_by_event_id
```

`_subscriptions` and `_subscription_names` are configuration-time registration state.
`_fingerprints_by_event_id` is runtime transition state used for deduplication and collision
detection.

### `TimingMonitor`

Current mutable member:

```text
_starts[(rule_id, asset_id, correlation_id)] = start_event
```

This is runtime state required to correlate a later end event with its matching start.

### `StreamConsumer`

Current mutable members:

```text
_active_session_by_source
_seen_sessions_by_source
_next_sequence_by_session
_results
```

These belong to transport admission. PR #20 moved activation/sequence commit after successful core
ingestion for a newly accepted envelope.

### `LineAlertCore`

`LineAlertCore` owns references to the profile, topology, Mosaic, timing monitor, diagnostic engine,
and optional diagnostic projection engine. Its own `ingest()` method does not expose an explicit
transaction object, state checkpoint, or rollback protocol.

### Constructed registries and analyzers

`BaselineRegistry`, `TopologyGraph`, `DiagnosticEngine`, and `TimingSignalAnalyzer` retain
configuration/index data. No per-event mutation was observed in the inspected evaluation paths, but
a complete implementation plan must confirm all methods and future extensions before classifying
them as immutable runtime dependencies.

## Current event transition

### Streaming admission path

```text
1. Read source/session/sequence evidence.
2. Reject invalid start, reused session, old sequence, or sequence gap without core ingestion.
3. Call LineAlertCore.ingest(event).
4. On success, commit pending session activation and next sequence.
5. Append StreamResult and return transport receipt plus PipelineResult.
```

This boundary now avoids committing a newly proposed source session before the core accepts the
event. It does not make internal core mutations reversible.

### Core ingestion path

```text
1. MachineProfile validates the event when a profile is configured.
2. FusionMosaic checks the event-id ledger.
3. For a new event id, FusionMosaic writes its fingerprint to the ledger.
4. FusionMosaic invokes matching subscribers in registration order.
5. TimingMonitor may store a start or remove a matching start and derive a TimingFinding.
6. FusionMosaic returns a delivery receipt and consumer outputs.
7. LineAlertCore selects TimingFinding outputs.
8. DiagnosticEngine derives bounded recommendations.
9. LineAlertCore returns PipelineResult.
```

There is no explicit commit boundary spanning steps 3 through 9.

## Failure-window inventory

### FW-01 — event ledger commits before subscriber success

Observed sequence:

```text
_fingerprints_by_event_id[event_id] = fingerprint
subscriber.handler(event)
```

If a handler raises, the event identity may remain recorded even though no successful receipt or
pipeline result was produced. A retry of the same event can then be classified as an exact duplicate
and skipped.

Required characterization:

- handler raises on first attempt;
- no successful receipt exists;
- retry behavior is observed;
- event-ledger state is inspected through externally meaningful behavior rather than private-state
  assertions where practical.

### FW-02 — temporal start removed before negative-delay validation

Observed sequence for a matching end event:

```text
start = _starts.pop(key, None)
delay = end.timestamp - start.timestamp
if delay < 0: raise
```

If the end timestamp precedes the start timestamp, the start has already been removed before the
exception. Retrying a corrected or re-evaluated end event against the same monitor may no longer
have the original start evidence.

Required characterization:

- ingest valid start;
- ingest invalid earlier end and observe rejection/exception;
- ingest a valid end for the same correlation;
- verify whether original start evidence remains available.

### FW-03 — earlier subscriber mutation survives later subscriber failure

Fusion Mosaic invokes matching subscribers in order. If subscriber A mutates its state and
subscriber B raises, no orchestration rollback restores subscriber A.

Required characterization:

- two deterministic test subscribers;
- first records prepared/committed state;
- second raises;
- verify whether first subscriber state survives;
- retry same event and observe deduplication behavior.

### FW-04 — diagnostic derivation occurs after Mosaic mutation

`LineAlertCore.ingest()` derives recommendations after `mosaic.publish()` returns. A failure in
recommendation or future downstream projection logic can occur after the event ledger and timing
state have already changed.

Required characterization:

- inject a bounded diagnostic failure without changing physical or operational scope;
- verify event and timing state after failure;
- verify retry behavior.

### FW-05 — no explicit state identity in replay evidence

Current replay demonstrates repeatability by constructing fresh cores and comparing outputs for the
same ordered events. It does not yet identify prior-state digest, resulting-state digest, schema
versions, fingerprint algorithm version, rule-set digest, topology digest, or kernel build.

Risk:

Two runs can appear comparable while relying on different ambient code/configuration versions.

Required characterization:

- enumerate every input that can affect output;
- prove no ambient `now`, `latest`, mutable global, environment variable, file lookup, or network
  call influences kernel results;
- define canonical serialization before hashing manifests or state.

## Existing verification coverage observed

Current tests cover, among other behavior:

- declared-consumer Mosaic delivery;
- idempotence for an exact duplicate after a successful first publication;
- rejection of divergent content under an existing event id;
- late and within-envelope timing behavior;
- correlation-id isolation;
- repeatability across two fresh cores for one event sequence;
- streaming session/sequence rejection and post-PR #20 session-commit hardening.

The inspected Mosaic and pipeline tests do not currently characterize subscriber-exception
atomicity, temporal-state preservation after an invalid end, multi-subscriber rollback, diagnostic
failure after Mosaic success, or retry after a failed core transition.

## Proposed test matrix for the next runtime increment

The next runtime pull request, only after ADR acceptance and Issue #15 enforcement, should begin
with tests for these cases:

| Test | Expected invariant |
| --- | --- |
| New event + first subscriber raises | Event is not treated as successfully consumed; retry can execute. |
| New event + second subscriber raises | First subscriber retains no committed partial mutation. |
| Start + end with negative delay | Original start state remains unchanged after rejection. |
| Valid retry after negative delay | Valid end can still pair with original start. |
| Diagnostic derivation raises | Event/timing state does not commit without a successful pipeline result. |
| Exact duplicate after successful commit | Duplicate remains idempotent and produces no repeated consumer effects. |
| Event-id collision after successful commit | Divergent content remains rejected. |
| Stream session transition + failed core transition | Session and sequence remain uncommitted, preserving PR #20 behavior. |
| Same manifest + same initial state + same build | Outputs and resulting-state digest are identical. |
| Different topology/rule/baseline version | Difference is explicit in manifest and output provenance. |

## Candidate implementation patterns

No pattern is selected by this inventory.

### Prepared transition deltas

Each stateful consumer returns an immutable proposed delta and outputs without mutating live state.
The orchestrator commits all deltas only after every stage succeeds.

Advantages:

- explicit and independently testable;
- natural state/result evidence;
- no rollback path required for expected failures.

Risks:

- requires interface changes to stateful consumers;
- future consumers must obey the prepare/commit protocol.

### Copy-on-write bounded state

Run the transition against bounded copied state, then swap references on success.

Advantages:

- straightforward for current small dictionaries;
- isolates failed attempts.

Risks:

- copying cost grows with state;
- careless nested mutable values can defeat isolation.

### Snapshot and rollback

Capture state before handler execution and restore it on failure.

Advantages:

- potentially smaller initial refactor.

Risks:

- rollback code can be less reliable than forward code;
- hidden side effects or future external calls cannot be safely rolled back;
- verifier becomes too complex as consumers grow.

Prepared immutable deltas are the leading candidate, but selection requires a bounded design review
and tests before implementation.

## Open questions

1. Is Fusion Mosaic intended to support arbitrary third-party stateful consumers, or only governed
   LineAlert-owned consumers with a transition protocol?
2. Should event deduplication represent `attempted`, `accepted`, and `committed` identities
   separately, or only committed identities plus separate failure evidence?
3. What is the bounded lifetime and eviction policy for event fingerprints and unmatched starts?
4. How are state checkpoints canonicalized without allowing the verifier to rewrite the evidence it
   judges?
5. Which configuration objects require semantic versions, content digests, or both?
6. Does diagnostic projection participate in the same atomic event transition or remain an explicit
   later caller over committed findings?
7. Which findings must be byte-for-byte stable versus semantically equivalent across schema
   versions?
8. What independent implementation will verify transition and replay digests?

## Recommended next gate

Do not move files or change runtime behavior from this inventory alone.

Required sequence:

```text
1. Verify Issue #15 review enforcement.
2. Obtain independent review of ADR-0002 and this inventory on the exact draft head.
3. Resolve open questions that affect the transaction contract.
4. Approve a test-only characterization increment.
5. Run exact-head CI and independent review.
6. Only then propose the smallest atomic-transition implementation.
```

Rollback for the current documentation increment is closure of the draft pull request without merge.
