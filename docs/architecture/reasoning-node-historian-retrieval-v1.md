# Reasoning Node historian retrieval v1

## Purpose

This increment connects the deterministic Reasoning Node context contract to LineAlert condition
history without giving the Reasoning Node database write authority, diagnostic authority, or
equipment authority.

The path is:

~~~text
TimescaleDB condition_measurements
  -> verified read-only session
  -> deterministic scoped SELECT
  -> retained authority / quality checks
  -> EvidenceCandidate(HISTORICAL_OBSERVATION)
  -> reasoning-context-bundle.v1
~~~

The adapter is a retrieval boundary. It does not diagnose a machine and it does not reinterpret
clock evidence.

## Repository reality at implementation

The implementation was created from PR #145's merged main and then rebased onto current main at
1f046d14ba68fdea134c35f7e344041264e30279 after PR #146 merged its synthetic lab
clock-telemetry adapter. PR #146 has no changed-file overlap with this increment.

Live GitHub showed no open pull requests at the final rebase check. The repository state file
continues to classify production runtime deployment, physical equipment connection, and equipment
control paths as not observed. Available equipment material remains synthetic/demo material; no
Labeler 2 OEM manual or commissioned machine package was observed.

Those facts constrain this increment to software retrieval plumbing and synthetic/lab verification.

## Why a separate read-only source exists

The existing TimescaleHistorian is a writer-capable service boundary. Its constructor calls
ensure_schema(), which executes schema DDL. Reusing that constructor would violate a strict
Reasoning Node read-only boundary.

ReadOnlyTimescaleConditionHistorySource therefore opens its own connection with:

~~~text
default_transaction_read_only=on
~~~

and verifies that session state with SHOW default_transaction_read_only before allowing queries.

The adapter itself contains only hard-coded parameterized SELECT statements. It does not expose
generic SQL execution.

## Query contract

HistorianConditionQuery always requires exact asset_id and supports optional deterministic filters:

- relationship_id
- episode_id
- cycle_id
- phase_id
- from_time
- to_time
- limit

Time bounds must be timezone-aware. Limit is bounded from 1 through 5000.

The database query fetches limit + 1 rows so truncation is explicit.

## Truncation policy

v1 fails closed on truncation.

If more matching history exists than the requested bound, no EvidenceCandidate is emitted and the
result reports HISTORIAN.RETRIEVAL_TRUNCATED.

The caller should narrow asset/relationship/episode/time scope rather than silently reasoning from
an incomplete matching history set.

## Retained authority gate

A condition row can become a historical EvidenceCandidate only when its retained
evidence_authority exactly matches the expected current retrieval authority:

- schema_version = linealert.condition-evidence-authority.v1
- authority_scope = HISTORIAN_WRITE_TIME_POLICY_AUTHORITY
- asset_id
- profile_id
- source_name
- source_sha256

The SHA-256 digest is normalized to lowercase before comparison.

This proves only that the persisted row retained matching LineAlert write-time configuration and
policy authority. It does not prove that the physical machine was in the claimed state.

## Quality and semantic admission

v1 requires quality == good before promoting a row into a reasoning candidate.

The candidate semantic_admitted flag means the row passed this bounded historian retrieval gate:
exact query scope, good recorded quality, and exact retained declared configuration authority.
It does not elevate the historian row into verified physical state.

## Provenance preservation

Each emitted candidate retains:

- historian observation_id
- exact asset_id and relationship_id
- episode/cycle/phase identity when present
- recorded operating_context
- retained evidence_authority
- retained clock_evidence
- observation timestamp
- source mode
- deterministic historian source identity
- configuration source name and SHA-256 provenance

Clock evidence is copied through unchanged. Offset, drift, uncertainty, and temporal admissibility
remain owned by the clock-evidence workstream.

## Configuration mismatch

The adapter preserves each row's recorded operating_context.configuration_version.

It does not decide whether that version is current. The merged reasoning-context-bundle.v1 remains
the authority for that decision:

- matching current configuration may enter the evidence lane;
- historical configuration mismatch becomes CONTEXT_ONLY;
- historical configuration does not become current root-cause proof.

## Authority boundary

The retrieval result always states authorized_action = false.

The following remain true:

~~~text
historian_record != verified_physical_state
historical_pattern != current_root_cause
retained_write_time_authority != physical_truth
recorded_quality_good != causal_proof
retrieval != diagnosis
recommendation != authorized_action
~~~

## Not established by v1

This increment does not establish:

- a vector database
- embeddings
- Ollama connectivity
- automatic document ingestion
- functional-temporal historian retrieval
- machine-observation historian retrieval
- operational-outcome retrieval
- production deployment
- physical equipment connectivity
- diagnosis
- root cause
- safe production change
- equipment control

Those remain separately bounded increments.
