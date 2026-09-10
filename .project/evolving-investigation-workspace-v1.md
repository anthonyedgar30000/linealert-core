# Evolving investigation workspace v1

Repository: `anthonyedgar30000/linealert-core`  
Base: `main@acfd9791fa4eef624098cf69805893389afd7ef2`  
Branch: `agent/evolving-investigation-workspace-v1`

## Objective

Add one bounded synthetic investigation workspace that keeps multiple working explanations visible, links from the active Plant Canvas concern, and evolves from the existing shared demo session and event journal.

## Permitted paths

- `docs/triage/index.html`
- `docs/triage/investigation-link-adapter.js`
- `docs/investigation/index.html`
- `docs/investigation-model.js`
- `docs/evolving-investigation-workspace.md`
- `profiles/synthetic-labeler2-investigation-v1.json`
- `tests/test_investigation_workspace.py`
- `.project/evolving-investigation-workspace-v1.md`

## Evidence and equipment scope

- Source evidence: existing synthetic browser demo session + synthetic event journal.
- Asset: synthetic `Labeler 2` only.
- Available equipment documentation: synthetic profiles and generic demo/runbook material only; no OEM commissioning package is claimed for this increment.
- Physical equipment connection: not authorized or introduced.
- Equipment control: not authorized or introduced.
- Deployment state: repository/public-demo publication is distinct from operational deployment; this increment claims no production deployment or physical verification.
- Repository lineage note: after the original planning read, `main` advanced from `89908003f59d9320ff54b4c2713627baf37ab4cc` to `acfd9791fa4eef624098cf69805893389afd7ef2` through probe/cleanup commits while retaining the same tree `1e2c6c59e99901e0171476b9d2c2f96e2ecc5515`. This branch is rebased onto the later exact head.

## Design constraints

- Keep a best-supported working explanation plus credible alternatives; do not force three when evidence does not support them.
- Investigation standing is qualitative, not a hidden probability.
- Prefer observation-only, reversible, low-disturbance, high-information steps before material changes.
- Preserve event chronology; do not rewrite earlier evidence when the working picture changes.
- Episode closure is an operational disposition, not a terminal causal verdict.
- No LLM hypothesis generation or automatic playbook promotion in v1.

## Verification

Expected repository gates:

```text
ruff check .
pytest
```

The new static tests verify the page/link/profile/model contract and the LineAlert authority boundaries. Exact-head CI on the pull request is required before merge consideration.

## Rollback

Close the pull request or revert the bounded repository commit. No equipment rollback is required because this increment introduces no equipment command, PLC write, production listener, or physical-machine change.
