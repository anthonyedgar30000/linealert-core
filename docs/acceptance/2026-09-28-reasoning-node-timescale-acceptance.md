# Reasoning Node Timescale acceptance — 2026-09-28

## Scope

This is a bounded live acceptance record for the merged Reasoning Node historian retrieval and
deterministic context-bundle path on the controlled local Intel NUC development environment.

It is synthetic lab evidence. It is not production equipment evidence and does not establish
physical machine state, current configuration applicability, root cause, safety approval, or
authorized action.

## Repository state

- repository: anthonyedgar30000/linealert-core
- merged main used for the initial live run: 720d0ea1c4252141b98529385dbd149d65f843aa
- initial main included merged PR #147 and PR #148
- PR #149 merged during implementation with no changed-file overlap
- final rebased main used for the repeated live run: 5b719850bcb30e166ef6501c326d1475bcbbd0be
- open pull requests at the final rebase check: none

## Local runtime

- host class: Intel NUC13ANKi5
- Docker Desktop status during acceptance: running
- Docker client: 29.6.1
- Docker Engine: 29.6.1
- Timescale image tag: timescale/timescaledb:latest-pg16
- image ID: sha256:f495f2bc25ca7596ca8e1606c6241ca250ccc56a0c082b9f2ec0d290e0126cd9
- container: linealert-historian-db
- container health: healthy
- listener: 127.0.0.1:5433
- accepted volume: linealert-core_linealert_historian_data

Docker Desktop was started in the user session with ProgramData and ALLUSERSPROFILE set to
C:\ProgramData only in that process tree, matching the bounded startup pattern documented by the
earlier local historian acceptance. The Windows com.docker.service service remained stopped and no
machine-wide service, registry, or environment change was made.

A first Compose invocation from the new worktree created a separate empty project-scoped volume:
linealert-reasoning-live-acceptance-v1_linealert_historian_data. It contained no accepted historian
dataset and was removed before the live acceptance.

The container was then recreated under the linealert-core Compose project so it mounted the
preserved accepted volume exactly.

## Retained dataset

Exact selection:

~~~text
asset_id = LABELER-DEMO-01
episode_id = condition-runtime-replay
relationship_id = relationship:label-presentation-delay
~~~

Observed retained rows:

~~~text
count = 10
first observed_at = 2026-07-19T14:10:00.240000+00:00
last observed_at  = 2026-07-19T14:10:18.550000+00:00
~~~

Configured authority:

~~~text
source_name = labeler_demo_config.json
source_sha256 = 23178eb902261c7cb6f40c26a277b400fd49580def199e237d28e69cda353354
~~~

## Live Reasoning Node acceptance

The live harness produced:

~~~text
schema = linealert.reasoning-historian-live-acceptance.v1
scope = controlled_synthetic_local_historian
passed = true
read_only_verified = true
truncated = false
candidate_count = 10
refusal_count = 0
clock_evidence_nonempty_count = 10
candidate_configuration_versions = []
current_configuration_applicability = UNASSESSED
bundle_sha256 = 2d54fe7869b8cfed6bd96e5e278868fe016b1c6f8bca0f35abe905ed8de6f900
~~~

All 14 checks passed:

- SOURCE.READ_ONLY_VERIFIED
- RETRIEVAL.NOT_TRUNCATED
- RETRIEVAL.NO_REFUSALS
- RETRIEVAL.NONEMPTY
- RETRIEVAL.EXPECTED_COUNT
- CANDIDATE.UNIQUE_IDENTITY
- CANDIDATE.SOURCE_BINDING
- CANDIDATE.CONFIG_PROVENANCE
- CANDIDATE.CLOCK_EVIDENCE_PRESERVED
- BUNDLE.SCHEMA
- BUNDLE.CANDIDATE_PARITY
- BUNDLE.DETERMINISTIC
- BUNDLE.NO_MODEL
- BUNDLE.NO_AUTHORITY_ESCALATION

The deterministic context bundle contained:

~~~text
candidate_count = 10
evidence_count = 10
context_only_count = 0
refusal_count = 0
model_invoked = false
authorized_action = false
diagnosis_established = false
~~~

Repeated assembly produced the same bundle SHA-256.

After PR #149 merged, the branch was rebased onto main at
5b719850bcb30e166ef6501c326d1475bcbbd0be. Repository-wide Ruff, scoped MyPy, the full pytest
suite, and the live 14-check acceptance were repeated successfully. The live bundle SHA-256
remained 2d54fe7869b8cfed6bd96e5e278868fe016b1c6f8bca0f35abe905ed8de6f900.

## Configuration-version limitation

The 10 preserved historian rows predate the current configuration-version preservation requirement
and have no operating_context.configuration_version value.

This acceptance therefore does not compare the historical rows with a declared current
configuration version. The evidence lane result above is valid only for a request that does not
assert current-configuration equivalence.

Current configuration applicability remains explicitly UNASSESSED.

## Clock-evidence boundary

All 10 admitted candidates preserved a non-empty clock_evidence payload.

This acceptance verifies preservation only. It does not independently verify NTP/PTP state,
reference topology, offset, drift, step-monitor completeness, or temporal admissibility. Those
semantics remain owned by the clock-evidence workstream.

## Acceptance result

~~~text
PASS — controlled synthetic local Timescale -> read-only Reasoning Node retrieval
       -> deterministic context bundle
~~~

## Rollback / runtime cleanup

The Timescale container can be stopped without -v so the accepted development volume is preserved.
Docker Desktop can then be stopped. No production equipment, controller, safety system, or
equipment-control path is involved.
