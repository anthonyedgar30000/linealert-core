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
PR32_HEAD = "9d9553440cafa89b2d184ccb7c82f5455fc9716a"
PR32_MERGE = "aa4c842447bde0bfc0ca32aab928409619e82893"


def load_project_state() -> dict[str, Any]:
    value = json.loads(PROJECT_STATE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_state_snapshot_advances_to_pr32_main() -> None:
    state = load_project_state()
    assert state["schema_version"] == "project.active-work.v1"
    assert state["repository"]["full_name"] == (
        "anthonyedgar30000/linealert-core"
    )
    assert state["state_model"]["captured_from_main"] == PR32_MERGE
    assert state["state_model"]["current_reality_source"] == (
        "live_github_and_explicit_user_direction"
    )
    assert "supersedes cached current-state claims" in (
        state["state_model"]["semantics"]
    )

    baseline = state["trusted_baseline"]
    assert baseline["commit"] == PR32_MERGE
    assert baseline["commit_role"] == "observed_main_head_after_pr32_merge"
    assert baseline["main_ci_status"] == (
        "not_exposed_or_not_verified_for_merge_commit"
    )

    completed = baseline["last_completed_increment"]
    assert completed["pull_request"] == 32
    assert completed["source_head"] == PR32_HEAD
    assert completed["merge_commit"] == PR32_MERGE
    assert completed["pull_request_ci"]["run_id"] == 30498588064
    assert completed["pull_request_ci"]["conclusion"] == "success"
    assert completed["pull_request_ci"]["checkout_provenance"] == (
        "literal_pull_request_head_sha"
    )
    assert completed["pull_request_ci"]["test_summary"] == (
        "74_passed_2_xfailed"
    )

    runtime = baseline["last_merged_runtime_increment"]
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
    assert runtime["deployment_status"] == "not_deployed"


def test_live_observation_matches_post_pr32_reality() -> None:
    observation = load_project_state()["live_observation"]
    assert observation["default_branch_head"] == PR32_MERGE
    assert observation["open_pull_requests_before_branch_creation"] == []
    assert observation["open_issues"] == [19, 23, 31]
    assert observation["adopted_governance_issue"] == 27
    assert observation["visibility"] == {
        "github_metadata": "public",
        "canonical_policy": "public",
        "status": "verified_public",
    }
    assert observation["deployment"] == "not_deployed"
    assert observation["azure_lab_resources"] == "not_created"
    assert observation["physical_equipment_connection"] == "not_observed"
    assert observation["network_listener"] == "not_observed"
    assert observation["equipment_control_path"] == "not_observed"
    assert "no_oem_or_commissioning" in observation["equipment_documentation"]


def test_active_azure_lab_workstream_preserves_tier_2_gate() -> None:
    state = load_project_state()
    assert len(state["workstreams"]) == 1
    workstream = state["workstreams"][0]
    assert workstream["workstream_id"] == (
        "microsoft-opc-plc-azure-iot-operations-lab-v1"
    )
    assert workstream["tracking_issue"] == 31
    assert workstream["runbook_pull_request"] == 32
    assert workstream["state"] == "open_blocked_before_stage_1_execution"
    assert workstream["next_stage"] == (
        "isolated_codespaces_k3s_quickstart_evidence_capture"
    )
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
    assert state["tracked_pull_requests"] == []


def test_issue_lifecycle_is_reconciled_without_overclaiming() -> None:
    issues = load_project_state()["issue_lifecycle"]

    issue_23 = issues["23"]
    assert issue_23["characterization"] == "completed_by_pr28"
    assert issue_23["remediation"] == "FW-01_and_FW-02_merged_by_pr29"
    assert issue_23["remaining_scope"] == [
        "FW-03_later_subscriber_rollback",
        "FW-04_diagnostic_derivation_rollback",
    ]
    assert "Do not close" in issue_23["closure_rule"]

    issue_19 = issues["19"]
    assert issue_19["state"] == "open_superseded_direction"
    assert issue_19["risk_tier"] == "tier_2"
    assert issue_19["successor_issue"] == 31
    assert issue_19["implementation_authority"] == "not_granted"

    issue_31 = issues["31"]
    assert issue_31["state"] == "open_blocked_before_stage_1_execution"
    assert issue_31["runbook_pull_request"] == 32
    assert issue_31["runbook_status"] == "merged"
    assert issue_31["azure_resources"] == "not_created"
    assert issue_31["qualified_review"] == "not_established"
    assert issue_31["implementation_authority"] == "not_granted"

    assert issues["27"] == {
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
    history = load_project_state()["governance_incident_history"]
    assert "Append-only incident keys" in history["historical_detail"]
    incidents = {item["id"]: item for item in history["incidents"]}
    required_ids = {
        "pr12-blocked-merge-2026-07-22",
        "pr13-zero-review-merge-2026-07-22",
        "pr14-zero-review-merge-2026-07-23",
        "pr16-zero-review-gate-bypass-2026-07-28",
        "pr17-zero-review-gate-bypass-2026-07-28",
        "pr20-zero-review-gate-bypass-2026-07-28",
        "pr21-review-gate-probe-merged-zero-review-2026-07-28",
        "pr22-zero-review-architecture-publication-2026-07-28",
        "pr24-explicit-no-merge-boundary-bypassed-2026-07-28",
        "pr29-merged-without-separately-recorded-named-authority-2026-07-29",
        "pr30-merged-without-separately-recorded-named-authority-2026-07-29",
        "pr32-merged-without-separately-recorded-named-authority-2026-07-29",
    }
    assert required_ids <= set(incidents)
    assert incidents[
        "pr32-merged-without-separately-recorded-named-authority-2026-07-29"
    ]["merge_commit"] == PR32_MERGE

    recent = history["recent_lifecycle"]
    assert [item.get("pull_request") for item in recent] == [
        25,
        None,
        28,
        29,
        30,
        None,
        32,
    ]
    assert recent[1]["issue"] == 27
    assert recent[5]["issue"] == 31


def test_governance_policy_separates_tier_1_and_tier_2() -> None:
    controls = load_project_state()["repository_controls"]
    historical = controls["historical_main_review_gate"]
    assert historical["tracking_issue"] == 15
    assert historical["status"] == "not_effective_or_not_verified"
    assert "Issue 27 replaced" in historical["supersession"]

    assert controls["tier_1_policy"] == {
        "tracking_issue": 27,
        "independent_github_approval_required": False,
        "fresh_named_merge_instruction_required": True,
        "exact_head_ci_required": True,
    }
    assert controls["tier_2_policy"] == {
        "tracking_issue": 27,
        "independent_or_qualified_review_required": True,
        "owner_approval_is_not_substitute_for_qualified_judgment": True,
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
    assert archaeology["anthonyedgar30000/linealert-analysis-engine"][
        "classification"
    ] == "merged_legacy_prototype_non_authoritative"
    assert "not_current_persistence" in archaeology[
        "anthonyedgar30000/HelixMemoryService"
    ]["disposition"]


def test_deployment_and_equipment_reality_remain_bounded() -> None:
    deployment = load_project_state()["deployment_state"]
    assert deployment == {
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
