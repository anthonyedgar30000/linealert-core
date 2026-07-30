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
PR36_HEAD = "a57d9ad5db12bbc5f7b510d59d5c1ee7c80ca9b9"
PR36_MERGE = "883e2648e6884c51c8f2269239c9f68bc0bad149"


def load_project_state() -> dict[str, Any]:
    value = json.loads(PROJECT_STATE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_state_snapshot_advances_to_pr36_main() -> None:
    state = load_project_state()
    assert state["schema_version"] == "project.active-work.v1"
    assert state["repository"]["full_name"] == "anthonyedgar30000/linealert-core"
    assert state["state_model"]["captured_from_main"] == PR36_MERGE
    policy = state["state_model"]["publication_policy"]
    assert policy["state_only_merge_requires_immediate_self_sync"] is False
    assert "substantive external lifecycle" in policy["rule"]

    observation = state["live_observation"]
    assert observation["default_branch_head"] == PR36_MERGE
    assert observation["open_pull_requests_before_branch_creation"] == []
    assert observation["open_issues"] == [23, 31]
    assert observation["recently_closed_issues"]["35"]["state"] == "closed_not_planned"
    assert observation["visibility"]["status"] == "verified_public"

    completed = state["trusted_baseline"]["last_completed_increment"]
    assert completed["pull_request"] == 36
    assert completed["source_head"] == PR36_HEAD
    assert completed["merge_commit"] == PR36_MERGE
    assert completed["pull_request_ci"]["run_id"] == 30508013490
    assert completed["pull_request_ci"]["checkout_provenance"] == (
        "literal_pull_request_head_sha"
    )
    assert completed["pull_request_ci"]["test_summary"] == "73_passed_2_xfailed"
    assert completed["submitted_reviews"] == 0


def test_runtime_atomicity_scope_remains_bounded() -> None:
    state = load_project_state()
    runtime = state["trusted_baseline"]["last_merged_runtime_increment"]
    assert runtime["pull_request"] == 29
    assert runtime["source_head"] == PR29_HEAD
    assert runtime["merge_commit"] == PR29_MERGE
    assert runtime["resolved_windows"] == [
        "FW-01_event_identity_commit",
        "FW-02_timing_start_evidence_preservation",
    ]
    assert runtime["remaining_windows"] == [
        "FW-03_later_subscriber_rollback",
        "FW-04_diagnostic_derivation_rollback",
    ]

    issue = state["issue_lifecycle"]["23"]
    assert issue["latest_verification"] == {
        "pull_request": 36,
        "ci_run": 30508013490,
        "test_summary": "73_passed_2_xfailed",
        "remaining_xfails": ["FW-03", "FW-04"],
    }


def test_stage1_authority_and_remaining_environment_gates() -> None:
    state = load_project_state()
    workstream = state["workstreams"][0]
    assert workstream["tracking_issue"] == 31
    assert workstream["state"] == (
        "owner_authorized_waiting_for_azure_environment_and_identity_package"
    )
    assert workstream["authority"] == {
        "owner_stage_1_authority": "granted_for_disposable_non_production_lab",
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
    assert workstream["linked_gate_disposition"] == {
        "issue": 35,
        "state": "closed_not_planned",
        "review_evidence_claimed": False,
        "scope": "bounded_disposable_stage1_only",
    }

    capability = workstream["capability_boundary"]
    assert capability["disposable_stage_1_azure_lab_after_environment_gates"] is True
    for field in {
        "offline_fixture_mapping_after_captured_evidence",
        "linealert_live_opcua_or_mqtt_adapter",
        "public_opcua_exposure",
        "credentials_in_repository",
        "physical_equipment_connection",
        "equipment_control",
    }:
        assert capability[field] is False


def test_issue_lifecycle_matches_corrected_stage1_decision() -> None:
    issues = load_project_state()["issue_lifecycle"]
    assert issues["35"] == {
        "title": "Qualify reviewer for Azure OPC PLC Stage 1",
        "state": "closed_not_planned",
        "parent_issue": 31,
        "review_evidence": "not_claimed",
        "disposition": "review_not_required_for_bounded_disposable_stage1",
        "later_scope_review_requirement": "preserved",
    }

    issue_31 = issues["31"]
    assert issue_31["state"] == "open_owner_authorized_waiting_for_environment"
    assert issue_31["independent_review_for_stage_1"] == (
        "not_required_by_current_owner_risk_decision"
    )
    assert issue_31["azure_resources"] == "not_created"
    assert issue_31["live_adapter_authority"] == "not_granted"

    tier_2 = load_project_state()["repository_controls"]["tier_2_policy"]
    assert tier_2["bounded_stage1_exception"]["owner_authority_sufficient"] is True
    assert "live_linealert_adapter" in tier_2["qualified_review_required_for"]
    assert "production_release" in tier_2["qualified_review_required_for"]


def test_pr36_concurrent_governance_change_is_preserved() -> None:
    history = load_project_state()["governance_incident_history"]
    incidents = {item["id"]: item for item in history["incidents"]}
    incident = incidents["pr36-concurrent-governance-change-not-reflected-2026-07-29"]
    assert incident["pr"] == 36
    assert incident["source_head"] == PR36_HEAD
    assert incident["merge_commit"] == PR36_MERGE
    assert incident["ci_run"] == 30508013490
    assert incident["classification"] == (
        "repository_state_sync_merged_after_issue35_closed_but_before_head_reconciled"
    )


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


def test_publication_and_readme_guidance_are_current() -> None:
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
        "azure_lab_resources": "not_created",
        "physical_equipment_connection": "not_observed",
        "network_listener": "not_observed",
        "equipment_control_path": "not_observed",
    }
