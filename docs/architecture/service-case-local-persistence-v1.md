# Service case local persistence v1

## Purpose

This increment gives the local Speedway Service Workspace durable service-case
and plant-reported-context storage across browser refreshes and local LineAlert
process restarts.

Persistence remains a local development / synthetic service boundary. It does
not create a plant CMMS record, a production service database, direct machine
evidence, or equipment authority.

## Runtime topology

The local hybrid stack adds one loopback-only Python service:

- `127.0.0.1:8768` — service-case persistence service
- `127.0.0.1:8766` — Next.js LineAlert frontend
- `127.0.0.1:8765` — existing evidence bridge
- `127.0.0.1:8767` — optional historian service

The browser, including a laptop on the same LAN, continues to use only the
Next.js frontend. Next.js same-origin API routes proxy service-case reads and
plant-context writes to the loopback persistence service.

The persistence service is not bound to the LAN.

## Storage

The service uses one JSON file per service case, named from a SHA-256 digest of
the service-case identity. The payload contains:

- the validated `linealert.service-case.v1` record;
- zero or more validated `linealert.plant-reported-context.v1` records;
- the local-store schema version;
- the latest local write timestamp;
- explicit non-authority fields.

Writes use a temporary file, flush + fsync, and `os.replace` into the retained
path while holding an in-process re-entrant lock.

This establishes bounded single-process atomic replacement. It does not claim a
distributed transaction, multi-host consistency, database durability semantics,
or rollback of unrelated external side effects.

## Default local path

The hybrid launcher stores records under the current Windows user's local
application-data directory:

`%LOCALAPPDATA%\LineAlert\service-cases-v1`

If that environment location is unavailable, the launcher falls back to a
repository-local `.runtime\service-cases-v1` directory.

The retained JSON is plaintext local data. Encryption-at-rest, authenticated
multi-user access, backup policy, and production retention policy are not
implemented in this increment.

## Seed behavior

The synthetic Speedway workspace seed is
`examples/speedway_service_case_workspace_seed_v1.json`.

The service seeds that case only when the identity is absent. Restarting the
service does not overwrite retained plant context or other later local changes.

The seed contains no unresolved plant-context references.

## Write path

Plant context is accepted only through the v1 contract. The service validates:

- exact service-case and plant-context schema versions;
- service-case identity in the request path;
- asset identity;
- context identity uniqueness;
- timezone-aware reported event timestamps;
- reported time shape;
- reported clock quality;
- source-verification state;
- provenance;
- exact service-case ↔ context reference binding.

Allowed manual verification states remain:

- `plant_relay_only`
- `technician_viewed_source`
- `technician_retained_copy`

There is no `direct_source_retrieval` state.

Caller-supplied authority booleans do not promote the record. Serialized output
continues to emit bounded false values for direct-system observation, verified
source record, causal claim, equipment authority, production-record authority,
and return-to-service authority.

## Failure behavior

If the local persistence service is unavailable:

- the workspace may still display its controlled synthetic fallback case;
- plant-context entry is disabled;
- the UI reports the local store as unavailable;
- no in-memory "saved" entry is substituted for failed persistence.

If a retained file is malformed or violates the service-case/context contracts,
that service-case read fails closed instead of silently accepting the record.

## Canonical boundaries

- local_persistence != plant_cmms_record
- local_persistence != production_service_database
- persisted_technician_entry != direct_system_observation
- persisted_plant_reported_context != verified_source_record
- single_process_atomic_replace != distributed_transaction
- service_case_persistence != equipment_authority
- service_case_persistence != return_to_service_authority

## Deferred

This increment does not add:

- direct customer CMMS access;
- authentication or authorization for production users;
- encrypted-at-rest records;
- multi-user concurrency;
- remote/cloud synchronization;
- retention/backup policy;
- automatic reasoning-node ingestion of plant-reported context;
- equipment control;
- safety or return-to-service authority.
