# Local Timescale acceptance — 2026-09-28

## Scope

This is a time-bounded acceptance record for the controlled synthetic LineAlert demo on a local Windows/WSL2 development host.

It is not production equipment evidence and does not establish physical connectivity, root cause, verified physical state, safe change, or authorized action.

## Source state

- repository: `anthonyedgar30000/linealert-core`
- merged `main`: `9a675026c0321e75ac39de1e76c2ee01677361e3`
- no open pull requests before the acceptance branch was created
- synthetic asset: `LABELER-DEMO-01`
- episode: `condition-runtime-replay`
- target relationship: `relationship:label-presentation-delay`
- configured policy: `label-presentation-persistence-v1`, revision `1`, criterion `3 of 4`
- config SHA-256: `23178eb902261c7cb6f40c26a277b400fd49580def199e237d28e69cda353354`

## Local database runtime

- Docker Desktop: 4.81.0
- Docker Engine: 29.6.1
- Timescale image tag: `timescale/timescaledb:latest-pg16`
- resolved image digest: `sha256:f495f2bc25ca7596ca8e1606c6241ca250ccc56a0c082b9f2ec0d290e0126cd9`
- container: `linealert-historian-db`
- health: `healthy`
- database listener: `127.0.0.1:5433`

The automation shell did not inherit `ProgramData` or `ALLUSERSPROFILE`. Docker Desktop therefore failed with `unable to get 'ProgramData'`. It was relaunched with both variables set to `C:\ProgramData` only in that process tree. No machine-wide environment or registry change was made.

## Schema evidence

The live `condition_measurements.evidence_authority` column was observed as:

```text
data_type = jsonb
is_nullable = YES
column_default = NULL
```

This matches the no-backfill/no-default contract from PR #141.

## Synthetic bridge evidence

The deterministic condition replay completed with:

```text
measurement_count = 10
refusal_count = 0
reason_code = EVIDENCE.CONDITION_RUNTIME_COMPLETE
```

## Persisted historian evidence

The historian reported `connected = true`, `source_available = true`, and one configured persistence policy.

The condition-history API returned:

```text
count = 10
truncated = false
authority-null rows = 0
distinct config SHA = 23178eb902261c7cb6f40c26a277b400fd49580def199e237d28e69cda353354
distinct target policy ID = label-presentation-persistence-v1
```

Direct SQL against Timescale returned:

```text
row_count = 10
authority_count = 10
authority_null_count = 0
first observed_at = 2026-07-19T14:10:00.240000+00:00
last observed_at = 2026-07-19T14:10:18.550000+00:00
```

## Live configured localization

The live historian localization endpoint returned:

```text
schema = linealert.configured-condition-localization.v1
disposition = READY
localization = PERSISTENCE_ESTABLISHED
first_outside = 2026-07-19T14:10:08.370000+00:00
persistence_established = 2026-07-19T14:10:12.430000+00:00
policy = label-presentation-persistence-v1
policy_revision = 1
criterion = 3 of 4
historian_write_time_policy_equivalence = VERIFIED
equivalence_reason = POLICY.HISTORICAL_AUTHORITY_EQUIVALENT
selected_record_count = 10
target_record_count = 10
retained_authority_count = 10
missing_authority_count = 0
incomplete_authority_count = 0
conflict_count = 0
```

`VERIFIED` remains bounded to historian write-time authority and does not prove identical source-runtime config bytes at the physical observation instant.

## Next.js application boundary

The same localization request was sent through `/api/historian/conditions/localize` on the live Next.js service.

Direct historian and proxy responses matched for:

- response schema;
- selection disposition;
- localization disposition;
- policy ID;
- policy revision;
- historian write-time policy-equivalence state;
- equivalence reason code.

The Operator View root returned HTTP 200 and contained the LineAlert application identity.

## Repeatable harness

The new `linealert.local-historian-acceptance.v1` harness passed all 14 checks against this live stack.

The harness performs GET requests and read-only SQL `SELECT` queries only.

## Acceptance result

```text
PASS — controlled synthetic local persistence/API/proxy chain
```

## Rollback

Transient bridge, historian, and Next.js processes can be stopped without altering evidence semantics. The Timescale container can be stopped or removed without `-v` to preserve the named development volume.

No production equipment, controller, safety system, or equipment-control path was involved in this acceptance.