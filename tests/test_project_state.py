from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_STATE = PROJECT_ROOT / ".project" / "active-work.json"
PROJECT_GUIDANCE = PROJECT_ROOT / ".project" / "README.md"
ROOT_README = PROJECT_ROOT / "README.md"
LINEAGE_GUIDANCE = PROJECT_ROOT / "docs" / "repository-lineage.md"

PR16_MERGE = "0720bbf269a571ec35a74829d72c124370afd436"
PR17_MERGE = "a094f0812ad85bfbcfe3c90c4cbc1d85547be7cd"
PR20_HEAD = "3f2e4b23154d34f892d6966fa1e9d72c5acb5087"
PR20_MERGE = "f0b48f7e8966f886ff29629af0fb2eb50e366ea4"
PR21_HEAD = "19d9ce75cbff57d45a911083b84761b7aef32842"
PR21_MERGE = "6858d4a639c0dc27853c313e545d3af467ec1412"
PR22_HEAD = "cc6718bf76329ac28f83429204a0d5ef4b36bfe9"
PR22_MERGE = "03060ff05252e43538f86ad75527be05c96853a5"
PR24_HEAD = "e9e7065e7062bc9b99bbe429999e77f01b07ed99"
PR24_MERGE = "9bc91562535f8fad681aecde61a6fc28885da69c"


def load_project_state() -> dict[str, Any]:
    value = json.loads(PROJECT_STATE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_state_snapshot_advances_to_pr24_main() -> None:
    state = load_project_state()
    assert state["schema_version"] == "project.active-work.v1"
    assert state["repository"]["full_name"] == "anthonyedgar30000/linealert-core"
    assert state["state_model"]["captured_from_main"] == PR24_MERGE
    assert state["state_model"]["current_reality_source"] == (
        "live_github_and_explicit_user_direction"
    )
    assert "supersedes cached current-state claims" in state["state_model"]["semantics"]

    baseline = state["trusted_baseline"]
    assert baseline["commit"] == PR24_MERGE
    assert baseline["commit_role"] == "verified_main_head_after_pr24_merge"

    completed = baseline["last_completed_increment"]
    assert completed["pull_request"] == 24
    assert completed["source_head"] == PR24_HEAD
    assert completed["merge_commit"] == PR24_MERGE
    assert completed["exact_head_ci"] == {
        "run_id": 30410780245,
        "conclusion": "success",
        "python_versions": ["3.11", "3.12"],
    }
    assert completed["review_status"] == "merged_with_zero_submitted_reviews"
    assert completed["authorization_status"] == (
        "merged_after_explicit_merge_not_authorized_boundary"
    )
    assert completed["runtime_change"] is False

    functional = baseline["last_functional_increment"]
    assert functional["pull_request"] == 20
    assert functional["source_head"] == PR20_HEAD
    assert functional["merge_commit"] == PR20_MERGE
    assert functional["exact_head_ci"]["run_id"] == 30388270765
    assert functional["review_status"] == "merged_with_zero_submitted_reviews"
    assert functional["deployment_status"] == "not_deployed"


def test_live_observation_records_intentionally_public_visibility() -> None:
    observation = load_project_state()["live_observation"]
    assert observation["default_branch_head"] == PR24_MERGE
    assert observation["open_pull_requests_before_branch_creation"] == []
    assert observation["open_issues"] == [15, 19, 23]
    assert observation["visibility"] == {
        "github_metadata": "public",
        "canonical_policy": "public",
        "status": "verified_public",
    }
    assert observation["deployment"] == "not_deployed"
    assert observation["physical_equipment_connection"] == "not_observed"
    assert observation["network_listener"] == "not_observed"
    assert observation["equipment_control_path"] == "not_observed"


def test_reconciliation_owns_exactly_three_paths() -> None:
    state = load_project_state()
    assert len(state["workstreams"]) == 1
    workstream = state["workstreams"][0]

    assert workstream["workstream_id"] == "state-reconciliation-after-pr24-v1"
    assert workstream["branch"] == "agent/reconcile-state-after-pr24-v1"
    assert workstream["pull_request_resolution"] == "resolve_live_by_exact_branch"
    assert workstream["classification"] == "state_and_documentation_only_reconciliation"
    assert workstream["permitted_paths"] == [
        ".project/active-work.json",
        "README.md",
        "tests/test_project_state.py",
    ]
    assert state["tracked_pull_requests"] == []

    capability = workstream["capability_boundary"]
    assert capability["pull_request_creation"] is True
    assert capability["pull_request_merge"] is False
    assert capability["state_reconciliation_only"] is True
    assert capability["documentation_correction"] is True
    for field in {
        "runtime_code_change",
        "workflow_change",
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


def test_governance_incidents_remain_distinct_through_pr24() -> None:
    history = load_project_state()["governance_incident_history"]
    assert "prior git revisions" in history["historical_detail"]

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

    assert incidents["pr16-zero-review-gate-bypass-2026-07-28"][
        "merge_commit"
    ] == PR16_MERGE
    assert incidents["pr17-zero-review-gate-bypass-2026-07-28"][
        "merge_commit"
    ] == PR17_MERGE

    pr20 = incidents["pr20-zero-review-gate-bypass-2026-07-28"]
    assert pr20["source_head"] == PR20_HEAD
    assert pr20["merge_commit"] == PR20_MERGE
    assert pr20["ci_run"] == 30388270765

    pr21 = incidents["pr21-review-gate-probe-merged-zero-review-2026-07-28"]
    assert pr21["source_head"] == PR21_HEAD
    assert pr21["merge_commit"] == PR21_MERGE
    assert pr21["ci_run"] == 30390768815

    pr22 = incidents["pr22-zero-review-architecture-publication-2026-07-28"]
    assert pr22["source_head"] == PR22_HEAD
    assert pr22["merge_commit"] == PR22_MERGE
    assert pr22["ci_run"] == 30407732572

    pr24 = incidents["pr24-explicit-no-merge-boundary-bypassed-2026-07-28"]
    assert pr24["source_head"] == PR24_HEAD
    assert pr24["merge_commit"] == PR24_MERGE
    assert pr24["ci_run"] == 30410780245
    assert pr24["classification"] == (
        "state_reconciliation_merged_after_explicit_merge_not_authorized_boundary"
    )

    for pr in (13, 14, 16, 17, 20, 21, 22, 24):
        incident = next(item for item in incidents.values() if item["pr"] == pr)
        assert incident["reviews"] == 0


def test_repository_controls_keep_review_gate_and_public_policy_separate() -> None:
    controls = load_project_state()["repository_controls"]
    review = controls["main_review_gate"]

    assert review["tracking_issue"] == 15
    assert review["observed_effect_through_pr24"] == "zero_review_merges_permitted"
    assert review["probe_pull_request"] == 21
    assert review["probe_result"] == "merged_with_zero_submitted_reviews"
    assert review["required_approvals"] == 1
    assert review["dismiss_stale_approvals"] is True
    assert review["prevent_owner_or_admin_bypass"] is True
    assert review["status"] == "not_effective_or_not_verified"
    assert review["tool_boundary"] == (
        "connected_github_toolset_does_not_expose_ruleset_mutation"
    )

    visibility = controls["repository_visibility"]
    assert visibility == {
        "github_metadata": "public",
        "canonical_policy": "public",
        "status": "verified_public",
        "policy_source": "explicit_user_direction",
        "next_gate": "none",
    }


def test_lineage_lifecycle_is_preserved() -> None:
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
    assert "not_current_persistence" in memory["disposition"]


def test_deployment_and_equipment_reality_remain_bounded() -> None:
    deployment = load_project_state()["deployment_state"]
    assert deployment == {
        "status": "not_deployed",
        "physical_equipment_connection": "not_observed",
        "network_listener": "not_observed",
        "equipment_control_path": "not_observed",
    }


def test_project_lookup_requires_repository_resolution() -> None:
    guidance = PROJECT_GUIDANCE.read_text(encoding="utf-8")
    assert "## Repository resolution gate" in guidance
    assert "exact `owner/repository` target" in guidance
    assert "stop without drawing ownership or project-state conclusions" in guidance
    assert "authoritative only for the resolved repository" in guidance
    assert "A correctly executed lookup against the wrong repository" in guidance


def test_root_readme_and_lineage_guidance_agree() -> None:
    readme = " ".join(ROOT_README.read_text(encoding="utf-8").split())
    lineage = LINEAGE_GUIDANCE.read_text(encoding="utf-8")

    assert (
        "`linealert-core`**: authoritative current LineAlert implementation"
    ) in readme
    assert "`ContextOS`**: separate execution-containment" in readme
    assert "`HelixMemoryService`**: early memory-service prototype" in readme
    assert (
        "not current LineAlert persistence, retrieval, or lifecycle-system "
        "authority"
    ) in readme
    assert "`main` is merged repository reality" in readme
    assert "Independent review is not established" in readme
    assert "**Assess replay timing against governed baselines**" in lineage
    assert "must not be merged into the current lineage" in lineage
    assert "merged_implementation != governance_gate_satisfied" in lineage
    assert "green_ci != authorized_merge" in lineage
    assert "historical_pattern != current_root_cause" in lineage
    assert "successful_test != safe_production_change" in lineage
