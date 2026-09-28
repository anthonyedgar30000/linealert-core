# Condition evidence authority provenance v1

This increment preserves historian write-time configuration and persistence-policy authority alongside newly persisted condition measurements.

It does not change persistent-localization semantics or upgrade any historical evidence by itself.

## Schema

`condition_measurements` gains one nullable JSONB field:

```text
evidence_authority
```

There is deliberately no default and no backfill.

That creates three distinct states:

```text
evidence_authority = NULL
  authority provenance was not retained for this row

evidence_authority.configuration != NULL
persistence_policy = NULL
  exact historian write-time config authority was retained,
  but that config had no persistence policy for this relationship

evidence_authority.configuration != NULL
persistence_policy != NULL
  exact historian write-time config authority and exact relationship
  persistence-policy binding were retained
```

Pre-#141 rows remain `NULL`. Replaying a duplicate historical observation does not silently enrich it because the existing primary-key conflict behavior remains `DO NOTHING`.

## Retained authority document

New rows written while the historian service has an asset-bound condition configuration can retain:

```text
schema_version:
  linealert.condition-evidence-authority.v1

authority_scope:
  HISTORIAN_WRITE_TIME_POLICY_AUTHORITY

configuration:
  asset_id
  profile_id
  source_name
  source_sha256

persistence_policy:
  policy ID
  policy revision
  relationship ID
  required_outside
  window_size
  authority class
  asset/profile/source/config-SHA provenance
```

The persistence-policy object is nullable when the relationship is declared by the loaded config but has no configured persistence policy.

## Write-time validation

Authority is attached only when:

- the observation asset matches the configured authority asset; and
- the observation relationship is declared by a temporal rule in that exact config.

A mismatch is refused rather than stamping unrelated configuration provenance onto the condition evidence.

If the historian service has no configured condition authority, the measurement may still be retained under the existing historian contract, but `evidence_authority` remains `NULL`.

## Meaning of write-time authority

`HISTORIAN_WRITE_TIME_POLICY_AUTHORITY` means:

> This was the exact machine-config/persistence-policy authority loaded by the historian service when it persisted this condition evidence.

It does **not** by itself prove:

- that the upstream condition-runtime process used the same config bytes to derive the observation;
- that the same policy was in force at the physical observation timestamp if persistence happened later;
- that the configured persistence policy is mechanically or physically correct;
- that the sensor value is verified physical state.

Those remain separate evidence questions.

## Read compatibility

`ConditionHistoryRecord` and `GET /api/history/conditions` now surface `evidence_authority`.

Legacy rows remain valid typed history records with:

```text
evidence_authority = null
```

No read-time inference fills that field.

## Localization consumption

The configured localization endpoint can now compare this retained write-time authority with the currently applied configured policy after the condition-history selector admits a complete evidence set.

The verifier reports:

```text
VERIFIED
UNVERIFIED
CONFLICT
```

Legacy rows with `evidence_authority = null` remain `UNVERIFIED`. No read-time inference or backfill upgrades them.

A `VERIFIED` result means historian write-time configuration/policy authority equivalence only. It does not prove that the upstream condition-runtime process used identical config bytes at the physical observation timestamp.

## Authority boundary

Retained authority provenance does not:

- convert an anomaly into a fault;
- establish root cause or causation;
- prove physical state;
- prove that a policy is optimal;
- authorize maintenance, engineering, production, or safety action;
- backfill missing historical provenance;
- override OEM or qualified human judgment.
