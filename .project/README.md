# LineAlert Core project state

This directory records bounded repository work ownership, lineage, and verification gates for `anthonyedgar30000/linealert-core`. It supports coordination across human and AI-assisted conversations; it does not replace live GitHub pull-request, CI, commit, deployment, equipment, or operational evidence.

## Repository resolution gate

Before inspecting project state or drawing any ownership, implementation, deployment, or verification conclusion:

1. Resolve and state the exact `owner/repository` target from explicit user direction, a repository or pull-request URL, or verified live repository metadata.
2. Confirm that the repository exists and that the branch, pull request, commits, CI, deployment evidence, and `.project/` files being inspected belong to that exact repository.
3. If the repository target is ambiguous or multiple repositories are plausible, stop without drawing ownership or project-state conclusions.
4. Treat lookup findings as authoritative only for the resolved repository; never transfer conclusions between repositories because they share a project name, conversation, organization, architecture, or history.

A correctly executed lookup against the wrong repository is not valid project evidence.

## Read order before writing

1. Pass the repository resolution gate and state the resolved `owner/repository` target.
2. Read `active-work.json` from that repository.
3. Confirm the live default branch, active branch, pull request, exact head SHA, changed files, CI, and deployment state in GitHub or the relevant deployment system.
4. Verify that no other conversation owns the same branch, objective, equipment scope, or file scope.
5. Inspect applicable equipment documentation, source identity, clock quality, calibration state, engineering units, sampling behavior, firmware, configuration, topology, test conditions, and operator interventions before changing telemetry or diagnostic behavior.
6. Work only within the declared permitted paths and capability boundary.
7. Treat protected paths and capabilities as unavailable unless a later bounded increment explicitly changes them.

## Reality precedence

- `main` governs merged repository reality.
- Live pull-request metadata, the exact current branch head, exact-head CI, and branch `.project/` state govern active work-in-progress reality.
- A green check proves only that the declared CI checks passed on the inspected commit.
- Chat history, generated reports, screenshots, and `.project/` records are coordination evidence, not substitutes for live repository, deployment, equipment, or operational evidence.

## State meanings

- `proposed`: described but not committed;
- `implemented_on_branch`: committed to the owned branch;
- `ci_verified`: the declared CI gates passed on the exact head;
- `merged`: GitHub records the pull request as merged;
- `deployed`: current deployment evidence proves an external deployment;
- `operationally_verified`: current runtime and equipment evidence prove the expected behavior under the recorded conditions.

These states are not interchangeable.

## LineAlert authority boundaries

```text
telemetry != diagnosis
anomaly != fault
correlation != causation
model_match != proof
recommendation != authorized_action
historical_pattern != current_root_cause
sensor_value != verified_physical_state
successful_test != safe_production_change
```

## Ownership rule

One bounded workstream owns one named branch and declared file scope. Other conversations are review-only unless ownership is explicitly transferred and recorded here.

After a pull request merges or closes, a state-only reconciliation should release its branch ownership before a new implementation increment begins.
