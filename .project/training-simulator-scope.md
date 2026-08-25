# Field-grounded training simulator workstream

Branch: `agent/field-grounded-training-simulator`

Base: `main` at `8b162a013f0fb2d88ae2bd97f4a5ce59bba0a594`

## Objective

Add a separate interactive plant-troubleshooting training route whose playable scenarios are admitted only from documented field failure patterns. Preserve the existing production-evidence and commissioning-test boundaries.

## File scope

- `ui/app/training/page.tsx`
- `ui/app/training/training.module.css`
- `ui/app/page.tsx`
- `docs/training-scenario-provenance.md`
- `.project/training-simulator-scope.md`

## Assumptions

- No OEM- or site-specific machine documentation is currently admitted in the repository for this training case.
- LA-T01 is therefore classified only as a field-documented pattern, not a site-validated incident.
- No numeric web-tension sensor, PLC tag, threshold, or adjustment value is assumed.

## Safety and authority boundary

The training route is educational. It does not authorize production changes, prove a real-machine root cause, or replace site/OEM procedures. Persona actions remain bounded by role; a successful exercise is not evidence that the same intervention is safe on production equipment.

## Verification

Expected checks on the exact branch head:

1. Python 3.11 and 3.12 lint/test matrix passes.
2. UI ESLint passes.
3. Next.js production build passes and includes `/training`.
4. Operator View continues to keep live evidence, training, and commissioning paths distinct.
5. Training route exposes no random fault generator and marks unestablished instrumentation as `NOT ASSUMED`.

## Rollback

Close the pull request without merge, or revert the branch commit(s). The change adds a route and documentation only; it does not modify telemetry ingestion, deterministic diagnostic logic, controller behavior, or production actuation.
