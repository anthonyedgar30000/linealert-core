from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_STATE = PROJECT_ROOT / ".project" / "active-work.json"
PROJECT_GUIDANCE = PROJECT_ROOT / ".project" / "README.md"
ROOT_README = PROJECT_ROOT / "README.md"
LINEAGE_GUIDANCE = PROJECT_ROOT / "docs" / "repository-lineage.md"
TRANSACTION_INVENTORY = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "current-dependency-and-transaction-inventory.md"
)
CI_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"

PR37_HEAD = "fc22177e1b855fd6f416f648330cd3416215a96c"
PR37_MERGE = "97256907cd428a8a0ba3dfb7d4020fa19a2485ee"
PR38_HEAD = "0d5d8180a5edffaeca8a9822800d7e729ef96327"
PR38_MERGE = "06f795e760c7ad360bc51e264f8c55238a2a60da"


def load_project_state() -> dict[str, Any]:
    value = json.loads(PROJECT_STATE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_state_snapshot_advances_to_pr38_main() -> None:
    state = load_project_state()
    assert state["schema_version"] == "project.active-work.v1"
    assert state["repository"]["full_name"] == (
        "anthonyedgar30000/linealert-core"
    )
    assert state["state_model"]["captured_from_main"] == PR38_MERGE

    policy = state["state_model"]["publication_policy"]
    assert policy["state_only_merge_requires_immediate_self_sync"] is False
    assert policy["publication_pr_self_reference_required"] is False
    assert "substantive external lifecycle" in policy["rule"]
    assert "PR 38" in policy["current_correction_reason"]

    observation = state["live_observation"]
    assert observation["default_branch_head"] == PR38_MERGE
    assert observation["open_pull_requests_before_branch_creation"] == []
    assert observation["open_issues"] == [31]
    assert observation["recently_closed_issues"]["23"] == {
        "state": "closed_completed",
        "closed_by_pull_request": 38,
        "reason": "all_four_atomic_ingestion_windows_resolved",
    }
    assert observation["visibility"]["status"] == "verified_public"


def test_pr38_runtime_atomicity_is_current_and_bounded() -> None:
    state = load_project_state()
    completed = state["trusted_baseline"]["last_completed_increment"]
    assert completed["pull_request"] == 38
    assert completed["source_head"] == PR38_HEAD
    assert completed["merge_commit"] == PR38_MERGE
    assert completed["pull_request_ci"] == {
        "run_id": 30516440394,
        "conclusion": "success",
        "python_versions": ["3.11", "3.12"],
        "checkout_provenance": "literal_pull_request_head_sha",
        "test_summary": "74_passed_0_xfailed",
    }
    assert completed["submitted_reviews"] == 0
    assert completed["deployment_status"] == "not_deployed"

    runtime = state["trusted_baseline"]["last_merged_runtime_increment"]
    assert runtime["pull_request"] == 38
    assert runtime["source_head"] == PR38_HEAD
    assert runtime["merge_commit"] == PR38_MERGE
    assert runtime["resolved_windows"] == [
        "FW-01_event_identity_commit",
        "FW-02_timing_start_evidence_preservation",
        "FW-03_later_subscriber_rollback",
        "FW-04_diagnostic_derivation_rollback",
    ]
    assert runtime["remaining_windows"] == []
    assert runtime["external_side_effect_rollback"] == "not_claimed"


def test_issue_23_is_closed_with_all_invariants_promoted() -> None:
    issue = load_project_state()["issue_lifecycle"]["23"]
    assert issue["state"] == "closed_completed"
    assert issue["final_remediation"] == "FW-03_and_FW-04_merged_by_pr38"
    assert issue["remaining_scope"] == []
    assert issue["latest_verification"] == {
        "pull_request": 38,
        "ci_run": 30516440394,
        "test_summary": "74_passed_0_xfailed",
        "remaining_xfails": [],
    }
    assert "arbitrary_external_side_effects_are_not_transactional" in (
        issue["limitations"]
    )
    assert "software_atomicity_does_not_establish_equipment_safety" in (
        issue["limitations"]
    )


def test_stage1_authority_and_environment_gates_remain_bounded() -> None:
    state = load_project_state()
    workstream = state["workstreams"][0]
    assert workstream["tracking_issue"] == 31
    assert workstream["state"] == (
        "owner_authorized_waiting_for_azure_environment_and_identity_package"
    )
    assert workstream["authority"] == {
        "owner_stage_1_authority": (
            "granted_for_disposable_non_production_lab"
        ),
        "independent_review_for_bounded_stage_1": (
            "not_required_by_current_owner_risk_decision"
        ),
        "qualified_review_for_later_live_or_production_scope": "required",
        "live_linealert_adapter_authority": "not_granted",
        "physical_equipment_authority": "not_granted",
        "equipment_control_authority": "not_granted",
    }
    assert workstream["blockers"] == [
        "no_azure_management_connection_available_in_current_workspace",
        (
            "disposable_subscription_region_resource_group_cleanup_owner_"
            "and_credential_custodian_not_recorded"
        ),
    ]

    capability = workstream["capability_boundary"]
    assert capability[
        "disposable_stage_1_azure_lab_after_environment_gates"
    ] is True
    for field in {
        "offline_fixture_mapping_after_captured_evidence",
        "linealert_live_opcua_or_mqtt_adapter",
        "public_opcua_exposure",
        "credentials_in_repository",
        "physical_equipment_connection",
        "equipment_control",
    }:
        assert capability[field] is False

    issue_31 = state["issue_lifecycle"]["31"]
    assert issue_31["azure_resources"] == "not_observed"
    assert issue_31["execution_environment"] == (
        "not_available_in_current_workspace"
    )
    assert issue_31["identity_resource_package"] == "not_recorded"
    assert issue_31["live_adapter_authority"] == "not_granted"


def test_pr37_and_pr38_lifecycle_evidence_is_preserved() -> None:
    state = load_project_state()
    previous = state["trusted_baseline"]["last_repository_state_increment"]
    assert previous["pull_request"] == 37
    assert previous["source_head"] == PR37_HEAD
    assert previous["merge_commit"] == PR37_MERGE
    assert previous["pull_request_ci"]["run_id"] == 30509312378
    assert previous["pull_request_ci"]["test_summary"] == (
        "72_passed_2_xfailed"
    )

    incidents = {
        item["id"]: item
        for item in state["governance_incident_history"]["incidents"]
    }
    pr38 = incidents["pr38-runtime-atomicity-merged-2026-07-30"]
    assert pr38["source_head"] == PR38_HEAD
    assert pr38["merge_commit"] == PR38_MERGE
    assert pr38["ci_run"] == 30516440394
    assert pr38["reviews"] == 0
    assert "not_observable" in pr38["classification"]


def test_ci_workflow_verifies_literal_event_sha() -> None:
    state = load_project_state()
    policy = state["ci_policy"]
    assert policy["required_checkout"] == "literal_event_sha"
    assert policy["pull_request_sha"] == (
        "github.event.pull_request.head.sha"
    )
    assert policy["push_sha"] == "github.sha"
    assert policy["verification"] == (
        "git_rev_parse_HEAD_must_equal_expected_sha"
    )

    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "name: Checkout pull-request head" in workflow
    assert "ref: ${{ github.event.pull_request.head.sha }}" in workflow
    assert "name: Checkout pushed commit" in workflow
    assert "ref: ${{ github.sha }}" in workflow
    assert "name: Verify exact checkout provenance" in workflow
    assert 'actual_sha="$(git rev-parse HEAD)"' in workflow
    assert 'test "$actual_sha" = "$EXPECTED_SHA"' in workflow


def test_transaction_inventory_matches_pr38_boundary() -> None:
    inventory = TRANSACTION_INVENTORY.read_text(encoding="utf-8")
    assert PR38_MERGE in inventory
    assert "PR #38" in inventory
    assert "`MosaicTransaction`" in inventory
    assert "FW-01" in inventory
    assert "FW-04" in inventory
    assert "resolved" in inventory
    assert "arbitrary external side effects" in inventory
    assert "software atomicity != equipment safety" in inventory


def test_publication_and_readme_guidance_remain_current() -> None:
    project_guidance = PROJECT_GUIDANCE.read_text(encoding="utf-8")
    assert "## Publication rule" in project_guidance
    assert "does not require another pull request merely to record its own merge" in (
        project_guidance
    )
    assert "live_scope_changed_before_merge = corrective_sync_required" in (
        project_guidance
    )

    readme = " ".join(ROOT_README.read_text(encoding="utf-8").split())
    assert "Issue #27 defines the risk-tiered workflow" in readme
    assert "Issue #15 acceptance evidence exists" not in readme
    assert "disposable Stage 1 simulator exception" in readme

    lineage = LINEAGE_GUIDANCE.read_text(encoding="utf-8")
    assert "green_ci != authorized_merge" in lineage
    assert "historical_pattern != current_root_cause" in lineage
    assert "successful_test != safe_production_change" in lineage


def test_deployment_and_equipment_reality_remain_bounded() -> None:
    assert load_project_state()["deployment_state"] == {
        "status": "not_deployed",
        "azure_lab_resources": "not_observed",
        "physical_equipment_connection": "not_observed",
        "network_listener": "not_observed",
        "equipment_control_path": "not_observed",
    }
