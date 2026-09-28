# Historical policy-equivalence verification v1

This increment verifies whether a complete selected condition-history evidence set retains historian write-time configuration and persistence-policy authority equivalent to the policy currently applied by configured localization.

It does not change persistence detection, dependency localization, condition admission, or historian selection.

## Evidence states

The verifier reports exactly one state:

```text
VERIFIED
UNVERIFIED
CONFLICT
```

These are evidence states, not equipment-health states.

## Verification scope

The verifier runs only after `ConditionHistorianSelector` returns `READY`.

Selector refusals such as truncation, empty history, missing target relationship, or context ambiguity remain:

```text
historical_policy_equivalence = UNVERIFIED
```

The verifier never certifies an incomplete or inadmissible selection.

## Exact matching rules

For every selected condition row, retained `evidence_authority.configuration` must match the currently applied binding on:

- asset ID;
- machine profile ID;
- machine-config SHA-256.

For every target-relationship row, retained `evidence_authority.persistence_policy` must additionally match:

- binding asset ID;
- binding profile ID;
- binding config SHA-256;
- policy ID;
- policy revision;
- relationship ID;
- `required_outside`;
- `window_size`;
- authority class.

The retained authority document must also use:

```text
schema_version = linealert.condition-evidence-authority.v1
authority_scope = HISTORIAN_WRITE_TIME_POLICY_AUTHORITY
```

A dependency row does not need the target relationship's persistence policy, but its retained configuration authority must match the selection's applied config.

## Deterministic state rules

`VERIFIED` requires:

- a complete admitted selection;
- at least one target-relationship row;
- complete retained authority on every selected row;
- matching configuration authority on every selected row;
- exact target-policy binding on every target row.

`UNVERIFIED` is returned when:

- authority is missing on any selected row;
- retained authority is structurally incomplete or uses an unsupported schema/scope;
- a target row has no retained persistence-policy binding;
- the selector did not admit the evidence set.

`CONFLICT` is returned when retained authority is complete enough to compare and concretely disagrees with the current applied config or target policy.

Conflict wins over missing/incomplete provenance if both are present because the selection contains positive contradictory authority evidence.

There is no majority vote, averaging, latest-wins selection, or implicit reconciliation.

## Response evidence

Configured localization keeps:

```text
policy_application.mode =
  CURRENT_CONFIG_APPLIED_TO_SELECTED_HISTORY
```

and now includes bounded policy-application evidence such as:

- `historical_policy_equivalence`;
- reason code;
- evidence basis;
- selected record count;
- target record count;
- retained authority count;
- missing/incomplete/conflict counts;
- first observation ID for each bounded exception class;
- authority boundary.

The evidence basis is:

```text
HISTORIAN_WRITE_TIME_POLICY_AUTHORITY
```

## Continued localization under conflict

A retained authority mismatch does not erase the raw historical measurements and does not rewrite the localization result.

The service may still report what happens when the **current configured policy** is applied to the selected historical evidence while separately reporting:

```text
historical_policy_equivalence = CONFLICT
```

That distinction prevents a current-policy analysis from masquerading as a historical-policy-equivalent analysis.

## Authority boundary

`VERIFIED` means:

> The complete selected evidence set retains historian write-time configuration authority matching the current config, and every target row retains the exact persistence-policy binding currently applied.

It does **not** prove:

- the upstream condition-runtime process used identical configuration bytes when it derived the observation;
- the same policy was active at the physical observation timestamp if historian persistence occurred later;
- the configured policy is physically optimal;
- persistence is a fault;
- causation or physical root cause;
- verified physical equipment state;
- authorization for maintenance, engineering, production, or safety action.

Those claims require separate evidence and authority.
