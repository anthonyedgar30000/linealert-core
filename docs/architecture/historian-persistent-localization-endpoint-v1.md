# Historian-backed persistent-localization endpoint v1

This increment exposes the already-governed condition-history selector and persistent dependency localizer through one read-only historian API.

The HTTP layer does not calculate persistence, infer dependency state, or reconstruct topology from database rows.

```text
HTTP query
   ↓
explicit bounded history selection
   ↓
target relationship
   ↓
configured persistence-policy resolution
   ↓
asset-bound configured topology authority
   ↓
ConditionHistorianSelector
   ↓
complete / non-truncated / single-context evidence?
   ├─ no  → bounded refusal
   └─ yes
        ↓
PersistentDependencyLocalizer
        ↓
serialized localization evidence package
```

## Endpoint

`GET /api/history/conditions/localize`

Required query fields:

- `asset_id`
- `selection_label`
- `target_relationship_id`

The selection must also be bounded by at least one of:

- `episode_id`
- `cycle_id`
- both timezone-aware `from_time` and `to_time`

Optional fields:

- `phase_id`
- `limit`

A `relationship_id` query filter is explicitly rejected for localization because it would hide dependency evidence.

`required_outside` and `window_size` are also rejected on this normal endpoint. The service resolves the configured persistence policy bound to `target_relationship_id` from the loaded machine configuration. Missing policy is a bounded refusal; no default rule is synthesized.

## Topology authority

Persistent dependency localization needs the declared dependency graph, including branches for which there may be no measurements in the selected window.

The service therefore does not reconstruct topology from historian rows.

The historian sidecar accepts:

```text
--condition-config <machine-config.json>
```

The config is loaded with the existing deterministic LineAlert configuration loader. The config must contain a machine profile so topology authority is bound to an exact asset and profile. Configured persistence policies are parsed from the same exact config bytes and must bind to relationships declared by temporal rules in that file.

The endpoint refuses an `asset_id` that does not match that configured asset.

Every successful or bounded localization response includes topology provenance:

- configured asset ID;
- machine profile ID;
- config source filename;
- SHA-256 of the exact config bytes used.

If the historian service was not started with an asset-bound condition config, the localization route returns HTTP 503 with:

```text
EVIDENCE.LOCALIZATION_TOPOLOGY_UNAVAILABLE
```

## Selection and localization authority

The endpoint delegates evidence completeness to `ConditionHistorianSelector`.

That selector can return bounded handoff dispositions such as:

- `READY`
- `REFUSED_TRUNCATED`
- `REFUSED_EMPTY`
- `REFUSED_TARGET_NOT_PRESENT`
- `REFUSED_RELATIONSHIP_FILTERED`
- `REFUSED_CONTEXT_AMBIGUOUS`

Only `READY` selections are passed to `PersistentDependencyLocalizer`.

The localizer remains the deterministic authority for:

- `first_outside_at`;
- `candidate_start_at`;
- `persistence_established_at`;
- the earliest qualifying N-of-M window;
- upstream/downstream relationship-window states.

The endpoint only parses, delegates, and serializes.

## Response boundary

The response uses:

```text
linealert.configured-condition-localization.v1
```

and contains:

- selection-request metadata;
- selection metadata and truncation state when history was read;
- selector/localization disposition and reason;
- the unchanged localization evidence package when admitted;
- configured persistence-policy ID, revision, N-of-M criterion, and config provenance;
- topology-authority provenance;
- policy-application semantics.

A missing configured policy returns `REFUSED_POLICY_NOT_CONFIGURED` with reason `POLICY.PERSISTENCE_NOT_CONFIGURED` and does not query condition history. A selector refusal is also a valid bounded result and does not trigger fallback localization.

Condition-history rows do not currently retain the machine-config SHA used by policy authority. Therefore the endpoint labels the configured-policy application as `CURRENT_CONFIG_APPLIED_TO_SELECTED_HISTORY` and marks `historical_policy_equivalence = UNVERIFIED`. It does not claim the currently loaded policy was necessarily the policy in force at the historical observation time.

## Hybrid demo

The local hybrid launcher now starts the historian with the existing synthetic labeler config as topology authority:

```text
examples/labeler_demo_config.json
```

That remains controlled synthetic/demo evidence. It is not an OEM commissioning package or production machine authority.

## Authority boundary

This endpoint does not:

- convert persistent deviation into a physical fault;
- establish causal direction;
- prove when a physical degradation process began;
- infer verified physical component state;
- synthesize or silently default the persistence rule;
- derive topology from observed data;
- call CADGrounded;
- write to equipment;
- authorize maintenance, production, engineering, or safety action.

It exposes deterministic persisted-evidence localization through a governed read-only API.
