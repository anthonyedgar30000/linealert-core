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
PR34_HEAD = "72d457a23f9e89cf3edfcff168f60e39e1f6e22c"
PR34_MERGE = "377d57bd64107fe602d03e7ae3f9727c26a07562"


def load_project_state() -> dict[str, Any]:
    value = json.loads(PROJECT_STATE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_state_snapshot_advances_to_pr34_main() -> None:
    state = load_project_state()
    assert state["schema_version"] == "project.active-work.v1"
    assert state["repository"]["full_name"] == "anthonyedgar30000/linealert-core"
    assert state["state_model"]["captured_from_main"] == PR34_MERGE
    assert "supersedes cached current-state claims" in state["state_model"]["semantics"]

    observation = state["live_observation"]
    assert observation["default_branch_head"] == PR34_MERGE
    assert observation["open_pull_requests_before_branch_creation"] == []
    assert observation["open_issues"] == [23, 31]
    assert observation["visibility"]["status"] == "verified_public"
    assert observation["recently_closed_issues"]["19"]["successor_issue"] == 31

    baseline = state["trusted_baseline"]
    assert baseline["commit"] == PR34_MERGE
    assert baseline["commit_role"] == "observed_main_head_after_pr34_merge"
    completed = baseline["last_completed_increment"]
    assert completed["pull_request"] == 34
    assert completed["source_head"] == PR34_HEAD
    assert completed["merge_commit"] == PR34_MERGE
    assert completed["pull_request_ci"]["run_id"] == 30503842026
    assert completed["pull_request_ci"]["conclusion"] == "success"
    assert completed["pull_request_ci"]["checkout_provenance"] == (
        "literal_pull_request_head_sha"
    )
    assert completed["pull_request_ci"]["test_summary"] == "71_passed_2_xfailed"
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
    assert issue["state"] == "open"
    assert issue["latest_verification"] == {
        "pull_request": 34,
        "ci_run": 30503842026,
        "test_summary": "71_passed_2_xfailed",
        "remaining_xfails": ["FW-03", "FW-04"],
    }


def test_tier_2_lab_authority_and_blockers_are_not_conflated() -> None:
    state = load_project_state()
    workstream = state["workstreams"][0]
    assert workstream["tracking_issue"] == 31
    assert workstream["state"] == (
        "owner_authorized_but_blocked_before_stage_1_execution"
    )
    assert workstream["authority"] == {
        "owner_stage_1_authority": "granted_for_disposable_non_production_lab",
        "qualified_independent_review": "not_established",
        "live_linealert_adapter_authority": "not_granted",
        "physical_equipment_authority": "not_granted",
        "equipment_control_authority": "not_granted",
    }
    assert workstream["blockers"] == [
        "no_azure_management_connection_available_in_current_workspace",
        "qualified_independent_reviewer_not_yet_identified",
        (
            "disposable_subscription_region_resource_group_cleanup_owner_"
            "and_credential_custodian_not_recorded"
        ),
    ]

    capability = workstream["capability_boundary"]
    assert capability["documentation_and_evidence_planning"] is True
    assert capability["disposable_stage_1_azure_lab_after_gates"] is True
    for field in {
        "offline_fixture_mapping_after_captured_evidence",
        "linealert_live_opcua_or_mqtt_adapter",
        "public_opcua_exposure",
        "credentials_in_repository",
        "physical_equipment_connection",
        "equipment_control",
    }:
        assert capability[field] is False


def test_issue_lifecycle_matches_selected_lab_direction() -> None:
    issues = load_project_state()["issue_lifecycle"]
    assert issues["19"] == {
        "title": "Plan isolated OpenPLC labeler lab emulator",
        "state": "closed_not_planned",
        "risk_tier": "tier_2",
        "successor_issue": 31,
        "disposition": "Microsoft_OPC_PLC_Azure_path_selected_first",
        "implementation_authority": "not_granted",
    }
    issue_31 = issues["31"]
    assert issue_31["state"] == (
        "open_owner_authorized_but_blocked_before_stage_1_execution"
    )
    assert issue_31["owner_stage_1_authority"] == (
        "granted_for_disposable_non_production_lab"
    )
    assert issue_31["azure_resources"] == "not_created"
    assert issue_31["qualified_review"] == "not_established"
    assert issue_31["live_adapter_authority"] == "not_granted"


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
    assert historical["observed_effect_through_pr34"] == (
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


def test_governance_incidents_remain_append_only_through_pr34() -> None:
    history = load_project_state()["governance_incident_history"]
    assert "Append-only incident keys" in history["historical_detail"]
    incidents = {item["id"]: item for item in history["incidents"]}
    assert incidents[
        "pr34-merged-without-separately-recorded-named-authority-2026-07-29"
    ] == {
        "id": (
            "pr34-merged-without-separately-recorded-named-authority-"
            "2026-07-29"
        ),
        "pr": 34,
        "state": "merged",
        "source_head": PR34_HEAD,
        "merge_commit": PR34_MERGE,
        "ci_run": 30503842026,
        "reviews": 0,
        "classification": (
            "repository_state_sync_merged_without_"
            "separately_recorded_named_authority"
        ),
    }
    recent = history["recent_lifecycle"]
    assert any(
        item.get("pull_request") == 34 and item.get("merge_commit") == PR34_MERGE
        for item in recent
    )
    assert recent[-2]["issue"] == 19
    assert recent[-2]["state"] == "closed_not_planned"
    assert recent[-1]["issue"] == 31
    assert recent[-1]["state"] == "open_owner_authorized_but_blocked"


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
