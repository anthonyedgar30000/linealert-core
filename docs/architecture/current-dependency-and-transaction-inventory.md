# Current dependency and transaction inventory

## Document status

Current read-only architecture inventory for
`anthonyedgar30000/linealert-core`.

Baseline inspected on August 2, 2026:

```text
main commit: 06f795e760c7ad360bc51e264f8c55238a2a60da
latest merged pull request: #38
open pull requests before the corrective sync: none observed
open issues: #31
repository visibility: public
PR #38 exact-head CI: success, run 30516440394
PR #38 test result: 74 passed, 0 xfailed
recorded deployment state: not_deployed
Azure lab resources: not observed
physical-equipment connection: not observed
network listener: not observed
equipment-control path: not observed
```

PR #38 supersedes the pre-transaction inventory previously recorded in this
document. The four deterministic ingestion windows tracked by Issue #23 are
now represented by ordinary passing tests. Issue #23 is closed as completed.

This inventory describes software structure and bounded transaction behavior.
It does not establish physical truth, current root cause, maintenance
authority, equipment safety, or production readiness.

## Available equipment context

The repository contains a pressure-sensitive labeler demo, machine profile,
process graph, timing envelopes, simulated or captured-event examples, and
related tests.

The August 2 repository search did not surface OEM manuals, electrical
drawings, pneumatic diagrams, safety assessments, calibration certificates,
controller backups, or physical commissioning records.

Consequently, this document makes no equipment-design, control, maintenance,
or safety claim.

## Responsibility map

### Contract-shaped modules

| Module | Current responsibility | Boundary observation |
| --- | --- | --- |
| `events.py` | Immutable `MachineEvent`, quality, canonical payload, and fingerprint | Event and source evidence; not verified physical state. |
| `machine.py` | Machine profile, components, dependencies, event bindings, and applicability validation | Versioned configuration boundary; validation is not diagnosis. |
| `topology.py` | Deterministic dependency graph and topology context | Expected relationship model; topology match is not root-cause proof. |
| `timing.py` | Temporal rules, timing findings, and unmatched-start state | Supplies checkpoint and restore callbacks for declared transaction participation. |
| `baseline.py` | Baseline records, invalidations, resolution, and drift assessment | Governed comparison; drift is not automatically a fault. |
| `diagnostics.py` | Bounded diagnostic recommendation derivation | Recommendation is not an authorized action. |
| `signal_processing.py` | Versioned deterministic signal assessment | Operates only on supplied evidence and policy. |
| `diagnostic_projection.py` | Symptom-first diagnostic projection | Downstream projection remains bounded by supplied findings and configuration. |

### Orchestration-shaped modules

| Module or class | Current responsibility | Current transaction boundary |
| --- | --- | --- |
| `mosaic.py` / `FusionMosaic` | Subscription registration, identity checks, provisional delivery, commit, and rollback | `prepare()` returns a one-use `MosaicTransaction`; event identity commits only after downstream success. |
| `mosaic.py` / `MosaicTransaction` | Hold provisional receipt and declared consumer checkpoints | `commit()` records event identity; `rollback()` restores declared checkpoints in reverse order. |
| `pipeline.py` / `LineAlertCore` | Validate, prepare delivery, derive findings and recommendations, then commit | Diagnostic failure triggers rollback before event identity is committed. |
| `timing.py` / `TimingMonitor` | Correlate explicit start/end events | `snapshot_state()` and `restore_state()` participate in the Mosaic-managed boundary. |

### Adapter-shaped modules

| Module | Current responsibility | Boundary observation |
| --- | --- | --- |
| `streaming.py` | Admit source sessions and sequence-valid envelopes before core ingestion | Transport evidence remains distinct from event meaning. |
| `replay.py` | Load ordered files, construct the core, and serialize results | Offline adapter; no network listener. |
| `baseline_io.py` | Load and serialize baseline evidence | File adapter around governed baseline behavior. |
| `signal_io.py` | Load signal-analysis input and policy | File and report adapter. |
| `diagnostic_io.py` | Load diagnostic profile, guide, and report evidence | File adapter; no physical verification. |
| `cli.py`, `diagnostic_cli.py` | Command-line composition | Local invocation boundary. |
| `simulator.py` | Produce bounded demo events | Simulator output is not verified equipment telemetry. |

## Mutable state inventory

### `FusionMosaic`

Runtime state includes the successful-event fingerprint ledger. Subscription
registration state is configuration-time state.

A new event is not added to the successful-event ledger during provisional
delivery. Identity is committed only by `MosaicTransaction.commit()`.

### `MosaicTransaction`

A transaction contains:

```text
provisional EventReceipt
optional event pending identity commit
declared consumer checkpoints
one-use finalized state
```

It can be committed or rolled back exactly once.

### `TimingMonitor`

Unmatched starts remain keyed by rule, asset, and correlation identity.
`TimingMonitor` supplies detached dictionary checkpoints for rollback.

### `StreamConsumer`

Transport admission retains active session, seen session, next sequence, and
result state. PR #20 already moved new-session commit after successful core
ingestion.

## Current core ingestion transition

```text
1. Validate event applicability against the configured machine profile.
2. Check committed event identity for duplicate or collision behavior.
3. Capture checkpoints for matching declared transactional consumers.
4. Deliver the event provisionally in deterministic subscription order.
5. Collect timing findings from provisional consumer outputs.
6. Derive bounded diagnostic recommendations.
7. On success, commit event identity and finalize the receipt.
8. On failure, restore declared checkpoints and leave identity uncommitted.
9. Return PipelineResult only after commit succeeds.
```

Rollback failures remain visible through `ExceptionGroup`. They are not
silently converted into success.

## Issue #23 failure-window status

| Window | Status | Current invariant |
| --- | --- | --- |
| FW-01 — handler failure commits event identity | resolved by PR #29 | A failed handler attempt leaves the event retryable. |
| FW-02 — invalid end consumes start evidence | resolved by PR #29 | A rejected negative delay preserves the matching start. |
| FW-03 — later subscriber failure retains earlier mutation | resolved by PR #38 | Declared Mosaic-managed consumer state is restored after later delivery failure. |
| FW-04 — diagnostic failure commits end transition | resolved by PR #38 | Diagnostic failure rolls back timing state and leaves the end event retryable. |

Exact-head PR #38 verification:

```text
head: 0d5d8180a5edffaeca8a9822800d7e729ef96327
CI run: 30516440394
Python 3.11: success
Python 3.12: success
Ruff: success
pytest: 74 passed
xfail: 0
submitted reviews: 0
```

## Transaction limitations

The transaction guarantee is intentionally narrow:

- only consumer state registered with paired checkpoint and restore callbacks
  participates;
- arbitrary external side effects are not reversible through this mechanism;
- databases, brokers, filesystems, cloud resources, PLCs, sensors, actuators,
  controllers, and production systems do not participate;
- restore failure is surfaced as incomplete rollback evidence;
- nested or concurrent publication is not claimed as supported;
- successful retry does not prove a root cause or physical condition.

```text
declared checkpoint != universal side-effect transaction
software atomicity != equipment safety
successful retry != root-cause proof
passing tests != deployment
recommendation != authorized action
```

## Remaining architecture and evidence gap

The earlier FW-05 observation remains separate from Issue #23: replay evidence
does not yet identify a prior-state digest, resulting-state digest, schema
versions, fingerprint algorithm version, rule-set digest, topology digest, and
kernel build in one canonical manifest.

That gap is not a failure of the PR #38 transaction invariant. Any replay
manifest increment requires separate scope, canonical serialization rules,
deterministic tests, and fresh authority.

## Verification expectations for future changes

Any later stateful consumer should be tested for:

- declared checkpoint and restore pairing;
- handler failure before commit;
- later-subscriber failure;
- downstream derivation failure;
- rollback failure visibility;
- valid retry after failure;
- exact duplicate after successful commit;
- divergent event-id collision after successful commit;
- stream-session behavior when core ingestion fails.

A consumer with undeclared or irreversible side effects remains outside the
current transaction guarantee.

## Current operational boundary

No repository evidence establishes:

- deployment of LineAlert Core;
- an Azure IoT Operations lab instance;
- a live OPC UA or MQTT adapter;
- a network listener;
- physical PLC, sensor, actuator, or controller connectivity;
- equipment commands or control;
- an OEM-approved or commissioned baseline.

Issue #31 remains the only open LineAlert Core issue. It governs a disposable
Microsoft simulator lab and remains blocked on an Azure-capable authenticated
environment and a recorded non-secret identity and cleanup package.

No runtime, adapter, deployment, or equipment-facing action is authorized by
this inventory alone.
