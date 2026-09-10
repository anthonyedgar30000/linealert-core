# Integrated investigation panel v1

Repository: `anthonyedgar30000/linealert-core`  
Base: `main@bf527e98481131ab83dc4f82027756830f5e6c06`  
Branch: `agent/integrate-investigation-panel-v1`

## Objective

Keep the synthetic Plant Canvas resident while the evolving investigation is open, so the simulator continues to advance and the investigation view remains attached to the same browser-local episode state.

## Permitted paths

- `docs/triage/investigation-link-adapter.js`
- `docs/investigation/index.html`
- `docs/evolving-investigation-workspace.md`
- `tests/test_investigation_workspace.py`
- `.project/integrated-investigation-panel-v1.md`

## Observed repository and deployment reality

- Base `main` is the merge of PR #115 at `bf527e98481131ab83dc4f82027756830f5e6c06`.
- Exact-head Python 3.11, Python 3.12, and UI-build checks on that merge are successful.
- No open pull requests were observed before this branch was created.
- The public GitHub Pages demo is a controlled synthetic static surface; production runtime deployment is not established by this increment.
- Available Labeler 2 material remains synthetic/demo material. No OEM manual, commissioned machine package, verified calibration package, physical-equipment connection, or equipment-control path is introduced or claimed.

## Problem reproduced from current implementation

The investigation link navigates away from Plant Canvas. Because the synthetic simulator executes in the Canvas document, same-tab navigation stops the active Canvas simulation and leaves the dedicated investigation page as a passive reader of the last persisted state.

The dedicated investigation page also requests its profile using `../../profiles/...`, which escapes the `/linealert-core/` GitHub Pages project path. The correct project-relative profile path from `/linealert-core/investigation/` is `../profiles/...`.

## Bounded change

- Preserve the existing dedicated investigation page and deterministic investigation model.
- Open that page inside a same-origin drawer/iframe over Plant Canvas for normal workflow use.
- Keep a full-page link for larger read-only viewing.
- Continue using the existing shared synthetic demo session and event journal; do not add a second episode state engine.
- Correct the investigation profile URL for the GitHub Pages project path.

## Boundaries

```text
working explanation != diagnosis
investigation priority != causal probability
test response != causal proof
navigation integration != new runtime authority
same-origin shared state != physical machine state
recommendation != authorized action
synthetic demo evidence != physical machine evidence
```

No LLM hypothesis generation, automatic lesson promotion, PLC write, equipment command, dispatch authority, production authorization, or safety approval is added.

## Verification

Expected repository gates:

```text
ruff check .
pytest
```

Static contract tests must verify that Plant Canvas opens the investigation as a dialog/iframe, the Canvas is not replaced by navigation, the full-page fallback remains available, and the investigation page loads the profile from the correct project-relative path. Exact-head CI is required before merge consideration.

## Failure modes and rollback

If the drawer fails to load, the underlying Canvas remains the existing synthetic simulator and the full-page investigation URL remains available. If the shared browser-local session is unavailable, the investigation view must remain read-only and make no equipment claim.

Rollback is repository-only: close the pull request or revert the bounded UI/documentation/test changes. No equipment rollback is required because this increment introduces no physical or control-path change.
