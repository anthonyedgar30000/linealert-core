from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_STATE = PROJECT_ROOT / ".project" / "active-work.json"
PROJECT_GUIDANCE = PROJECT_ROOT / ".project" / "README.md"
ROOT_README = PROJECT_ROOT / "README.md"
LINEAGE_GUIDANCE = PROJECT_ROOT / "docs" / "repository-lineage.md"
CI_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"

PR20_HEAD = "3f2e4b23154d34f892d6966fa1e9d72c5acb5087"
PR20_MERGE = "f0b48f7e8966f886ff29629af0fb2eb50e366ea4"
PR28_HEAD = "cb03bb10d8b3854272177380b8e3a9abe6a4788b"
PR28_MERGE = "9ab27c2f825f2c3ccea99fafbca0127fbe25fb05"
PR29_HEAD = "9146a12078394cfda22ff3e6bb9df22eaf53adaf"


def load_project_state() -> dict[str, Any]:
    value = json.loads(PROJECT_STATE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_state_snapshot_advances_to_pr28_main() -> None:
    state = load_project_state()
    assert state["schema_version"] == "project.active-work.v1"
    assert state["repository"]["full_name"] == (
        "anthonyedgar30000/linealert-core"
    )
    assert state["state_model"]["captured_from_main"] == PR28_MERGE
    assert state["state_model"]["current_reality_source"] == (
        "live_github_and_explicit_user_direction"
    )
    assert "supersedes cached current-state claims" in (
        state["state_model"]["semantics"]
    )

    baseline = state["trusted_baseline"]
    assert baseline["commit"] == PR28_MERGE
    assert baseline["commit_role"] == "verified_main_head_after_pr28_merge"

    completed = baseline["last_completed_increment"]
    assert completed["pull_request"] == 28
    assert completed["source_head"] == PR28_HEAD
    assert completed["merge_commit"] == PR28_MERGE
    assert completed["pull_request_ci"]["run_id"] == 30419929640
    assert completed["pull_request_ci"]["conclusion"] == "success"
    assert completed["pull_request_ci"]["checkout_provenance"] == (
        "github_pull_request_synthetic_merge_ref"
    )

    runtime = baseline["last_merged_runtime_increment"]
    assert runtime["pull_request"] == 20
    assert runtime["source_head"] == PR20_HEAD
    assert runtime["merge_commit"] == PR20_MERGE
    assert runtime["deployment_status"] == "not_deployed"


def test_live_observation_matches_branch_creation_reality() -> None:
    observation = load_project_state()["live_observation"]
    assert observation["default_branch_head"] == PR28_MERGE
    assert observation["open_pull_requests_before_branch_creation"] == [29]
    assert observation["open_issues"] == [19, 23]
    assert observation["adopted_governance_issue"] == 27
    assert observation["visibility"] == {
        "github_metadata": "public",
        "canonical_policy": "public",
        "status": "verified_public",
    }
    assert observation["deployment"] == "not_deployed"
    assert observation["physical_equipment_connection"] == "not_observed"
    assert observation["network_listener"] == "not_observed"
    assert observation["equipment_control_path"] == "not_observed"
    assert "no_oem_or_commissioning" in observation["equipment_documentation"]


def test_active_workstreams_preserve_scope_and_authority() -> None:
    state = load_project_state()
    workstreams = {item["workstream_id"]: item for item in state["workstreams"]}
    assert set(workstreams) == {
        "remediate-atomic-ingestion-v0.1",
        "reconcile-ci-and-project-state-v1",
    }

    remediation = workstreams["remediate-atomic-ingestion-v0.1"]
    assert remediation["pull_request"] == 29
    assert remediation["head"] == PR29_HEAD
    assert remediation["exact_head_ci_status"] == "not_yet_established"
    assert remediation["merge_authority"] == "not_granted"
    assert len(remediation["remaining_characterized_windows"]) == 2

    reconciliation = workstreams["reconcile-ci-and-project-state-v1"]
    assert reconciliation["branch"] == (
        "agent/reconcile-ci-and-project-state-v1"
    )
    assert reconciliation["pull_request"] == 30
    assert reconciliation["permitted_paths"] == [
        ".github/workflows/ci.yml",
        ".project/active-work.json",
        "tests/test_project_state.py",
    ]
    assert reconciliation["merge_authority"] == "not_granted"
    capability = reconciliation["capability_boundary"]
    assert capability["pull_request_creation"] is True
    assert capability["pull_request_merge"] is False
    assert capability["workflow_change"] is True
    assert capability["coordination_state_change"] is True
    for field in {
        "runtime_code_change",
        "dependency_change",
        "telemetry_connector",
        "network_listener",
        "persistence_change",
        "baseline_or_diagnostic_change",
        "deployment_mutation",
        "credential_use",
        "physical_equipment_connection",
        "equipment_control",
        "action_authorization",
        "repository_ruleset_mutation",
        "repository_visibility_mutation",
    }:
        assert capability[field] is False

    assert state["tracked_pull_requests"] == [29, 30]


def test_issue_lifecycle_is_reconciled_without_overclaiming() -> None:
    issues = load_project_state()["issue_lifecycle"]

    issue_23 = issues["23"]
    assert issue_23["title"] == "Track atomic ingestion failure windows"
    assert issue_23["characterization"] == "completed_by_pr28"
    assert issue_23["remediation"] == "two_of_four_windows_proposed_in_pr29"
    assert issue_23["remaining_scope"] == [
        "FW-03_later_subscriber_rollback",
        "FW-04_diagnostic_derivation_rollback",
    ]
    assert "Do not close" in issue_23["closure_rule"]

    issue_19 = issues["19"]
    assert issue_19["title"] == "Plan isolated OpenPLC labeler lab emulator"
    assert issue_19["state"] == "open_blocked"
    assert issue_19["risk_tier"] == "tier_2"
    assert issue_19["implementation_authority"] == "not_granted"

    issue_27 = issues["27"]
    assert issue_27 == {
        "title": "Adopt risk-tiered solo-maintainer governance policy",
        "state": "closed_completed",
        "role": "active_governance_policy",
    }


def test_ci_workflow_verifies_literal_event_sha() -> None:
    state = load_project_state()
    policy = state["ci_policy"]
    assert policy["required_checkout"] == "literal_event_sha"
    assert policy["pull_request_sha"] == "github.event.pull_request.head.sha"
    assert policy["push_sha"] == "github.sha"
    assert policy["verification"] == "git_rev_parse_HEAD_must_equal_expected_sha"

    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "name: Checkout pull-request head" in workflow
    assert "ref: ${{ github.event.pull_request.head.sha }}" in workflow
    assert "name: Checkout pushed commit" in workflow
    assert "ref: ${{ github.sha }}" in workflow
    assert "name: Verify exact checkout provenance" in workflow
    assert (
        "EXPECTED_SHA: ${{ github.event.pull_request.head.sha || github.sha }}"
        in workflow
    )
    assert 'actual_sha="$(git rev-parse HEAD)"' in workflow
    assert 'test "$actual_sha" = "$EXPECTED_SHA"' in workflow


def test_governance_incidents_remain_append_only() -> None:
    state = load_project_state()
    history = state["governance_incident_history"]
    assert "Append-only incident keys" in history["historical_detail"]

    incidents = {item["id"]: item for item in history["incidents"]}
    assert set(incidents) == {
        "pr12-blocked-merge-2026-07-22",
        "pr13-zero-review-merge-2026-07-22",
        "pr14-zero-review-merge-2026-07-23",
        "pr16-zero-review-gate-bypass-2026-07-28",
        "pr17-zero-review-gate-bypass-2026-07-28",
        "pr20-zero-review-gate-bypass-2026-07-28",
        "pr21-review-gate-probe-merged-zero-review-2026-07-28",
        "pr22-zero-review-architecture-publication-2026-07-28",
        "pr24-explicit-no-merge-boundary-bypassed-2026-07-28",
    }
    assert incidents[
        "pr24-explicit-no-merge-boundary-bypassed-2026-07-28"
    ]["classification"] == (
        "state_reconciliation_merged_after_explicit_merge_not_authorized_boundary"
    )

    recent = history["recent_lifecycle"]
    assert [item.get("pull_request") for item in recent] == [25, None, 28, 29, 30]
    assert recent[1]["issue"] == 27


def test_governance_policy_separates_tier_1_and_tier_2() -> None:
    controls = load_project_state()["repository_controls"]

    historical = controls["historical_main_review_gate"]
    assert historical["tracking_issue"] == 15
    assert historical["probe_pull_request"] == 21
    assert historical["status"] == "not_effective_or_not_verified"
    assert "Issue 27 replaced" in historical["supersession"]

    tier_1 = controls["tier_1_policy"]
    assert tier_1 == {
        "tracking_issue": 27,
        "independent_github_approval_required": False,
        "fresh_named_merge_instruction_required": True,
        "exact_head_ci_required": True,
    }

    tier_2 = controls["tier_2_policy"]
    assert tier_2["tracking_issue"] == 27
    assert tier_2["independent_or_qualified_review_required"] is True
    assert tier_2[
        "owner_approval_is_not_substitute_for_qualified_judgment"
    ] is True

    visibility = controls["repository_visibility"]
    assert visibility == {
        "github_metadata": "public",
        "canonical_policy": "public",
        "status": "verified_public",
        "policy_source": "explicit_user_direction",
    }


def test_lineage_archaeology_statuses_are_preserved() -> None:
    lineage = load_project_state()["repository_lineage"]
    assert lineage["authoritative"] == ["anthonyedgar30000/linealert-core"]

    archaeology = lineage["design_archaeology"]
    assert archaeology["anthonyedgar30000/LineAlertDemo"]["pull_requests"] == {
        "1": "merged",
        "2": "merged",
        "3": "open",
    }
    analysis = archaeology["anthonyedgar30000/linealert-analysis-engine"]
    assert analysis["pull_requests"] == {"1": "merged"}
    assert analysis["classification"] == (
        "merged_legacy_prototype_non_authoritative"
    )
    memory = archaeology["anthonyedgar30000/HelixMemoryService"]
    assert memory["pull_requests"] == {}
    assert "not_current_persistence" in memory["disposition"]


def test_deployment_and_equipment_reality_remain_bounded() -> None:
    deployment = load_project_state()["deployment_state"]
    assert deployment == {
        "status": "not_deployed",
        "physical_equipment_connection": "not_observed",
        "network_listener": "not_observed",
        "equipment_control_path": "not_observed",
    }


def test_project_lookup_and_lineage_guidance_remain_bounded() -> None:
    guidance = PROJECT_GUIDANCE.read_text(encoding="utf-8")
    assert "## Repository resolution gate" in guidance
    assert "exact `owner/repository` target" in guidance
    assert "stop without drawing ownership or project-state conclusions" in guidance
    assert "authoritative only for the resolved repository" in guidance

    readme = " ".join(ROOT_README.read_text(encoding="utf-8").split())
    lineage = LINEAGE_GUIDANCE.read_text(encoding="utf-8")
    assert "`linealert-core`**: authoritative current LineAlert implementation" in readme
    assert "`ContextOS`**: separate execution-containment" in readme
    assert "`HelixMemoryService`**: early memory-service prototype" in readme
    assert "not current LineAlert persistence" in readme
    assert "`main` is merged repository reality" in readme
    assert "Independent review is not established" in readme
    assert "must not be merged into the current lineage" in lineage
    assert "green_ci != authorized_merge" in lineage
    assert "historical_pattern != current_root_cause" in lineage
    assert "successful_test != safe_production_change" in lineage
