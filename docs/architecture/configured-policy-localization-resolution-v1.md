# Configured-policy localization resolution v1

This increment removes caller-selected persistence criteria from the normal historian localization API.

The target relationship remains explicit, but the N-of-M criterion is now resolved from the machine configuration already loaded as localization authority.

## Normal request flow

```text
asset + bounded history selection + target relationship
        ↓
resolve configured policy for target relationship
        ↓
policy found?
   no   → REFUSED_POLICY_NOT_CONFIGURED
   yes
        ↓
use exact policy N-of-M
        ↓
ConditionHistorianSelector
        ↓
PersistentDependencyLocalizer
        ↓
configured localization response
```

The normal endpoint rejects `required_outside` and `window_size`. A caller cannot override a configured relationship policy by changing URL parameters.

## Missing policy

No configured policy is treated as a governed refusal:

```text
disposition = REFUSED_POLICY_NOT_CONFIGURED
reason_code = POLICY.PERSISTENCE_NOT_CONFIGURED
```

The historian is not queried in this case because no authorized configured persistence criterion exists for the requested relationship.

There is no global N-of-M default.

## Resolved policy provenance

A successful or selector-refused configured localization carries the exact resolved policy binding:

- policy ID;
- policy revision;
- relationship ID;
- N-of-M values;
- authority class;
- asset ID;
- profile ID;
- config filename;
- config SHA-256.

The topology authority and policy binding originate from the same loaded configuration bytes.

## Historical-policy limitation

The original v1 condition-history rows preserved operating-context JSON such as configuration version, firmware, recipe, cycle, and phase when supplied, but did not retain the machine-config SHA used by persistence-policy authority.

Newer condition-history writes can retain nullable historian write-time configuration/policy authority provenance, while pre-existing rows remain without it.

After the selector admits a complete condition-history evidence set, the configured-localization endpoint compares retained authority with the currently applied policy and reports one of:

```text
historical_policy_equivalence = VERIFIED
historical_policy_equivalence = UNVERIFIED
historical_policy_equivalence = CONFLICT
```

Verification requires:

- matching asset/profile/config SHA across every selected row;
- complete retained authority on every selected row; and
- on every target-relationship row, the exact current policy ID, revision, relationship, N-of-M values, authority class, and matching binding config SHA.

Missing legacy provenance remains `UNVERIFIED`. A concrete retained mismatch is `CONFLICT`. A selector refusal such as truncation or context ambiguity also remains `UNVERIFIED` because equivalence is not evaluated from an inadmissible selection.

This prevents a later configuration from silently masquerading as historical write-time policy truth.

The result is still bounded to historian write-time authority. It does **not** prove that the upstream condition-runtime process used identical config bytes at the physical observation timestamp.

## Ad-hoc analysis boundary

The lower-level deterministic localizer and selector still accept an explicit `PersistenceRule`.

That keeps lab, sandbox, experiment, or test analysis possible without exposing arbitrary N-of-M values through the normal technician HTTP path.

```text
lower-level explicit rule
    != configured policy authority
    != commissioned policy proof
```

No ad-hoc rule is silently relabeled as configured.

## Response contract

The endpoint returns:

```text
linealert.configured-condition-localization.v1
```

with:

- configured-policy resolution/refusal state;
- bounded history selection state;
- persistent-localization evidence when admitted;
- policy provenance;
- policy-application semantics;
- topology provenance.

Selector refusals such as truncation or context ambiguity preserve the resolved configured policy in the response because the criterion was resolved successfully even though the evidence set was not admissible.

## Authority boundary

Configured-policy resolution does not:

- prove the configured N-of-M is physically optimal;
- prove that a historical incident used the same policy revision;
- convert persistence into a fault;
- establish causation;
- identify verified physical component state;
- authorize equipment intervention;
- override OEM, safety, engineering, or qualified human requirements.
