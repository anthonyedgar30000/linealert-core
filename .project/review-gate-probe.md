# Main review-gate verification probe

This file exists only to verify repository governance controls on `main`.

It does not change LineAlert runtime behaviour, tests, workflows, deployment, telemetry, diagnostics, baselines, adapters, credentials, persistence, or equipment-control capability.

## Required observations

Before this pull request may close as a successful governance test, preserve evidence that:

1. the repository is private;
2. the pull request targets `main`;
3. required CI checks complete successfully;
4. the repository owner cannot merge with zero approvals;
5. at least one approval is required from an identity other than `anthonyedgar30000`;
6. stale approvals are dismissed after the head changes;
7. administrator or owner bypass is not permitted;
8. force pushes and deletion of `main` are blocked.

```text
probe_pr_created != review_gate_verified
merge_button_visible != merge_authorized
owner_action != independent_approval
configuration_intended != control_enforced
```

This probe must not be merged merely to demonstrate that a merge is possible. Its purpose is to demonstrate that an unapproved merge is blocked.
