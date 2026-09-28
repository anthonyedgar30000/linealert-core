# Configured persistence policy v1

This increment moves persistence criteria out of presentation concerns and into declared machine configuration.

It does not change the persistent-localization algorithm or make the historian endpoint automatically select a configured policy yet.

## Policy identity

A configured persistence policy contains:

- stable `policy_id`;
- explicit `policy_revision`;
- exact semantic `relationship_id`;
- `required_outside`;
- `window_size`;
- authority class;
- optional descriptive metadata.

The N-of-M values are validated by the existing `PersistenceRule` contract.

## Exact relationship binding

Policy relationships use the same condition identity already emitted by LineAlert:

```text
relationship:<temporal rule_id>
```

When a machine configuration is loaded for localization, every configured persistence policy must bind to a relationship declared by a temporal rule in that same file.

Unknown relationships are refused.

Within one configuration, policy IDs must be unique and only one configured policy may bind a given relationship. There is no implicit precedence or “latest policy wins” behavior.

## Configuration provenance

The historian localization authority now loads topology and persistence policies from the same exact config bytes.

A resolved `ConfiguredPersistencePolicyBinding` retains:

- policy ID and policy revision;
- exact relationship ID;
- N-of-M criterion;
- asset ID;
- machine profile ID;
- config filename;
- SHA-256 of the exact configuration bytes.

Changing a policy revision or any other config bytes creates distinct source provenance. Historical policy meaning is therefore not silently rewritten by a later config file.

## Missing policy

A relationship without a configured persistence policy resolves to no policy.

```text
missing policy != use 3-of-4
missing policy != global default
```

A caller that requires configured policy authority must refuse or remain unresolved.

## Demo configuration

The controlled synthetic labeler demo now declares:

```text
policy_id:          label-presentation-persistence-v1
policy_revision:    1
relationship_id:    relationship:label-presentation-delay
required_outside:   3
window_size:        4
classification:     controlled_synthetic_demo
```

This is demo configuration, not an OEM commissioning package and not production engineering authority.

## Ad-hoc criteria

The policy model distinguishes `DECLARED_CONFIGURATION` from `AD_HOC_EXPERIMENT`.

This increment only parses configured policies from machine configuration. An explicit ad-hoc criterion remains conceptually distinct and must never be relabeled as configured or commissioned evidence.

## Endpoint integration

The historian-backed localization endpoint now resolves the configured persistence policy for the requested target relationship.

Normal HTTP localization no longer accepts caller-supplied `required_outside` or `window_size`. Those values come from the exact configured policy binding loaded with the machine topology authority.

A missing configured policy produces a bounded refusal rather than a fallback rule.

Lower-level Python APIs still accept an explicit `PersistenceRule`, which preserves a separate lab/experiment path without relabeling that criterion as configured authority.

## Authority boundary

Configured persistence policy does not:

- prove that its N-of-M criterion is physically optimal;
- prove a fault or causal mechanism;
- establish the true start of degradation;
- authorize equipment intervention;
- override OEM, safety, engineering, or qualified human requirements.

It makes the persistence criterion explicit, named, versioned, relationship-bound, and reviewable.
