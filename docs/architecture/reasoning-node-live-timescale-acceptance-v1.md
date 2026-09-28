# Reasoning Node live Timescale acceptance v1

## Purpose

This increment makes the merged Reasoning Node historian path repeatably testable against the
controlled local Timescale database on the Intel NUC.

It verifies the path:

~~~text
existing Timescale condition history
  -> verified read-only database session
  -> reasoning_historian deterministic retrieval
  -> provenance-bound EvidenceCandidate records
  -> reasoning-context-bundle.v1
~~~

The acceptance harness is deliberately downstream of runtime startup. It does not start Docker,
create schema, seed rows, or invoke an LLM.

## Read-only boundary

The harness uses ReadOnlyTimescaleConditionHistorySource from the merged historian-retrieval
increment. That source opens the database session with default_transaction_read_only=on and verifies
the setting before retrieval.

The live acceptance does not perform a trial write. A failed trial write could become a real write
if the boundary were misconfigured, so the acceptance relies on the verified database session
setting plus the source implementation's hard-coded parameterized SELECT surface.

## Authority source

The harness loads examples/labeler_demo_config.json through the same configured topology-authority
loader used by the historian service.

The exact asset, profile, source filename, and source SHA-256 are converted into
HistorianRetrievalAuthority. A retained historian row is admitted only if the merged retrieval
adapter validates that write-time authority exactly.

## Acceptance checks

The live report requires all of the following:

1. database read-only mode is verified;
2. selected history is not truncated;
3. no historian retrieval refusal exists;
4. the selected candidate set is non-empty;
5. the expected candidate count matches when configured;
6. candidate evidence identities are unique;
7. every candidate retains verified source binding, semantic admission, and the expected historian authority class;
8. every candidate retains exact configuration-file provenance;
9. retained clock-evidence payloads are present when required;
10. the context bundle uses linealert.reasoning-context-bundle.v1;
11. every selected candidate reaches the evidence lane when no current configuration version is asserted;
12. repeated bundle assembly is deterministic and yields the same SHA-256;
13. no model is invoked;
14. no diagnosis or action authority is granted.

## Configuration-version limitation

The preserved July synthetic historian rows used by the current local acceptance do not contain
operating_context.configuration_version.

The harness therefore reports:

~~~text
current_configuration_applicability = UNASSESSED
candidate_configuration_versions = []
~~~

This is not an acceptance failure because the acceptance scope is the persisted read-only retrieval
and context-assembly path. It is an explicit limitation: the result does not establish that the
historical records match a currently commissioned configuration.

A future dataset that claims current applicability must preserve a declared configuration version
or another governed equivalence mechanism and must pass the existing reasoning-context gate.

## Clock boundary

Clock evidence is preserved and counted, but this harness does not interpret it.

Offset estimation, step invalidation, step-monitor coverage, uncertainty, and temporal
admissibility remain owned by the clock-evidence workstream. A non-empty clock-evidence payload
does not by itself establish synchronized clocks or causal event ordering.

## Runtime lifecycle

The local Timescale container may be started against the preserved development volume before
running the harness. The harness itself does not own container startup or shutdown.

The expected local data volume is linealert-core_linealert_historian_data.

A Compose invocation from a differently named worktree can create a different project-scoped
volume. That volume must not be mistaken for the accepted retained evidence set.

## CLI

After the historian dependency is installed:

~~~powershell
linealert-reasoning-historian-acceptance --dsn <local DSN> --config examples/labeler_demo_config.json --asset-id LABELER-DEMO-01 --relationship-id relationship:label-presentation-delay --episode-id condition-runtime-replay --expected-candidate-count 10
~~~

The DSN is not written into the acceptance report.

## Claim boundary

~~~text
historian_record != verified_physical_state
historical_pattern != current_root_cause
retained_write_time_authority != physical_truth
clock_evidence_present != clock_synchronization_proven
retrieval != diagnosis
recommendation != authorized_action
successful_acceptance != safe_production_change
~~~

## Not established

This increment does not establish:

- current configuration applicability;
- production runtime deployment;
- physical equipment connectivity;
- OEM or commissioned-machine authority;
- embeddings or vector retrieval;
- Ollama or any other model invocation;
- diagnosis or root cause;
- safe maintenance or production action;
- equipment control.
