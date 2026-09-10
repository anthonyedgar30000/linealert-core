# Guide card context v1

## Scope

Preserve the Labeler 2 guide / spacing inspection result and subsequent restore action directly on the Plant Canvas asset card during the active OPC UA troubleshooting episode.

## Repository baseline

- Base branch: `main`
- Base commit: `953a21b486a5da1bf738933e52beb4d4d30f66b1`
- Prior increment: PR #124, guide inspection wording and explicit observed result
- Open PRs observed before branch creation: none
- Unrelated open work remains outside this increment, including issue #31

## Change

Add a presentation-only `guide-card-context-adapter.js` loaded after the guide-control adapter. It derives already-recorded workflow facts from the active episode history and renders them as a separate strip inside the Labeler 2 card:

```text
OBSERVED
Guide / spacing 2.1 mm outside the marked reference

ACTION
Guide / spacing restored to marked reference

VERIFY EFFECT
Awaiting 5-container trial
```

As the bounded trial and production verification proceed, only the `VERIFY EFFECT` presentation advances. The observation and action remain visible for the active episode.

## Ownership boundary

The existing OPC UA render-ownership adapter continues to own `nodeState` and the machine-state card labels. This increment inserts a sibling workflow-context element after `nodeState`; it does not overwrite OPC UA machine state.

```text
OPC UA machine state != human observation
human observation != diagnosis
recorded restore action != verified effect
intervention followed by improvement != proof of mechanism
```

## Safety / authority

No emulator state, OPC UA transport, bridge API, source admission, fast-forward, concern threshold, simulator control action, restoration prerequisite, trial logic, production verification criterion, PLC write, physical equipment connection, OEM authority, safety approval, or production authorization changes.

## Verification

- Contract test verifies adapter load order after guide control.
- Contract test verifies observation, restore, and effect labels are preserved.
- Contract test verifies the adapter does not write `nodeState.textContent`.
- CI is required before merge.
- Local acceptance after merge should confirm the Labeler 2 card shows the observation before restore, preserves it after restore, adds the restore action, and shows `Awaiting 5-container trial` until the bounded test is armed.
