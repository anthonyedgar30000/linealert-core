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

PR29_HEAD = "9146a12078394cfda22ff3e6bb9df22eaf53adaf"
PR29_MERGE = "e8bd1b7bb58112609acf27c2576abe967eda4731"
PR33_HEAD = "8af94c7e6436a6819c15fcfb6b1cf5106afa509a"
PR33_MERGE = "edbcd4fc8ba2d839f985be7ca190e138b365ddb4"


def load_project_state() -> dict[str, Any]:
    value = json.loads(PROJECT_STATE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_state_snapshot_advances_to_pr33_main() -> None:
    state = load_project_state()
    assert state["schema_version"] == "project.active-work.v1"
    assert state["repository"]["full_name"] == "anthonyedgar30000/linealert-core"
    assert state["state_model"]["captured_from_main"] == PR33_MERGE
    assert "supersedes cached current-state claims" in state["state_model"]["semantics"]

    observation = state["live_observation"]
    assert observation["default_branch_head"] == PR33_MERGE
    assert observation["open_pull_requests_before_branch_creation"] == []
    assert observation["visibility"]["status"] == "verified_public"

    baseline = state["trusted_baseline"]
    assert baseline["commit"] == PR33_MERGE
    assert baseline["commit_role"] == "observed_main_head_after_pr33_merge"
    completed = baseline["last_completed_increment"]
    assert completed["pull_request"] == 33
    assert completed["source_head"] == PR33_HEAD
    assert completed["merge_commit"] == PR33_MERGE
    assert completed["pull_request_ci"]["run_id"] == 30500687408
    assert completed["pull_request_ci"]["conclusion"] == "success"
    assert completed["pull_request_ci"]["checkout_provenance"] == (
        "literal_pull_request_head_sha"
    )


def test_runtime_and_tier_2_boundaries_remain_bounded() -> None:
    state = load_project_state()
    runtime = state["trusted_baseline"]["last_merged_runtime_increment"]
    assert runtime["pull_request"] == 29
    assert runtime["source_head"] == PR29_HEAD
    assert runtime["merge_commit"] == PR29_MERGE
    assert runtime["remaining_windows"] == [
        "FW-03_later_subscriber_rollback",
        "FW-04_diagnostic_derivation_rollback",
    ]

    workstream = state["workstreams"][0]
    assert workstream["tracking_issue"] == 31
    assert workstream["state"] == "open_blocked_before_stage_1_execution"
    assert workstream["blockers"] == [
        "no_azure_management_connection_available_in_current_workspace",
        "qualified_independent_reviewer_not_yet_identified",
        "stage_1_credential_and_deployment_authority_not_granted",
    ]
    capability = workstream["capability_boundary"]
    assert capability["documentation_and_evidence_planning"] is True
    for field in {
        "offline_fixture_mapping_after_captured_evidence",
        "azure_resource_creation",
        "credential_use",
        "opcua_client_or_listener",
        "mqtt_subscriber",
        "physical_equipment_connection",
        "equipment_control",
    }:
        assert capability[field] is False


def test_issue_15_and_governance_reality_are_not_overclaimed() -> None:
    state = load_project_state()
    issue_15 = state["issue_lifecycle"]["15"]
    assert issue_15 == {
        "title": "Enforce independent review on main before further merges",
        "state": "closed_not_planned",
        "acceptance_status": "not_satisfied",
        "superseded_by_issue": 27,
    }

    controls = state["repository_controls"]
    historical = controls["historical_main_review_gate"]
    assert historical["observed_effect_through_pr33"] == (
        "zero_review_merges_permitted"
    )
    assert historical["status"] == "not_effective_or_not_verified"
    assert controls["tier_1_policy"]["exact_head_ci_required"] is True
    assert controls["tier_2_policy"]["independent_or_qualified_review_required"] is True


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
    assert 'actual_sha="$(git rev-parse HEAD)"' in workflow
    assert 'test "$actual_sha" = "$EXPECTED_SHA"' in workflow


def test_governance_incidents_remain_append_only_through_pr33() -> None:
    history = load_project_state()["governance_incident_history"]
    assert "Append-only incident keys" in history["historical_detail"]
    incidents = {item["id"]: item for item in history["incidents"]}
    assert incidents[
        "pr33-merged-without-separately-recorded-named-authority-2026-07-29"
    ] == {
        "id": "pr33-merged-without-separately-recorded-named-authority-2026-07-29",
        "pr": 33,
        "state": "merged",
        "source_head": PR33_HEAD,
        "merge_commit": PR33_MERGE,
        "ci_run": 30500687408,
        "reviews": 0,
        "classification": (
            "project_state_and_azure_gate_reconciliation_merged_without_"
            "separately_recorded_named_authority"
        ),
    }
    recent = history["recent_lifecycle"]
    assert recent[-1]["pull_request"] == 33
    assert recent[-1]["merge_commit"] == PR33_MERGE


def test_deployment_and_equipment_reality_remain_bounded() -> None:
    assert load_project_state()["deployment_state"] == {
        "status": "not_deployed",
        "azure_lab_resources": "not_created",
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
