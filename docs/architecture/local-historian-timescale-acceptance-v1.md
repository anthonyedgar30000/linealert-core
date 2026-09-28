# Local historian Timescale acceptance v1

This contract verifies the controlled synthetic LineAlert persistence path against a live local TimescaleDB instance.

The acceptance command is read-only. It does not start Docker, write historian rows, reset volumes, mutate configuration, or interact with equipment.

## Command

```powershell
linealert-historian-acceptance --dsn "postgresql://linealert:linealert_dev@127.0.0.1:5433/linealert"
```

Equivalent module invocation:

```powershell
.\.venv\Scripts\python.exe -m linealert_core.historian_acceptance --dsn "postgresql://linealert:linealert_dev@127.0.0.1:5433/linealert"
```

The DSN may also be supplied through `LINEALERT_HISTORIAN_DSN`.

## Preconditions

The command assumes these services are already running:

- synthetic evidence bridge on `127.0.0.1:8765`;
- historian service on `127.0.0.1:8767`;
- TimescaleDB/PostgreSQL reachable through the supplied DSN;
- Next.js Operator View on `127.0.0.1:8766`.

Service startup is intentionally outside the acceptance command so verification cannot silently change the system it is observing.

## Default synthetic scope

```text
asset_id = LABELER-DEMO-01
episode_id = condition-runtime-replay
target_relationship_id = relationship:label-presentation-delay
expected_policy = label-presentation-persistence-v1 rev 1
```

These are controlled synthetic demo identities, not commissioned production equipment identities.

## Required checks

The command fails closed unless every check passes.

### Historian and history

It verifies that the historian is connected, the source is available, the requested asset matches the configured authority, the selected history is non-empty and non-truncated, every selected row retains `evidence_authority`, and all retained config SHAs equal the historian authority SHA.

Target rows must retain the expected persistence policy ID.

### Direct Timescale evidence

The database connection is opened with `default_transaction_read_only=on` and the command performs SQL `SELECT` statements only.

It verifies database/API row-count parity, no null authority on selected rows, matching config SHA, and the expected target policy ID.

### Configured localization

The controlled synthetic acceptance requires:

```text
disposition = READY
localization.disposition = PERSISTENCE_ESTABLISHED
historical_policy_equivalence = VERIFIED
reason_code = POLICY.HISTORICAL_AUTHORITY_EQUIVALENT
```

The configured policy ID and revision must also match the expected demo policy.

### Next proxy parity

The command compares the direct historian localization response with `/api/historian/conditions/localize` and requires exact parity for schema, selection disposition, localization disposition, policy ID/revision, equivalence state, and equivalence reason code.

### UI availability

The Operator View root must return HTTP 200 and contain the LineAlert application identity.

This confirms application availability only; it does not independently prove every client-side pixel or interaction.

## Output

The command emits `linealert.local-historian-acceptance.v1` with one PASS/FAIL result per check and an overall `passed` field. Any failed check or I/O error produces a non-zero exit code.

## Authority boundary

A passing result means the controlled synthetic local persistence/API/proxy chain is internally consistent under the evidence observed by the command.

It does not establish production equipment connectivity, commissioned machine authority, OEM approval, physical root cause, verified physical state, future failure, safe production change, or authorized maintenance/engineering/production/safety action.

Historian write-time policy equivalence remains distinct from proof that the upstream runtime used identical config bytes at the physical observation timestamp.