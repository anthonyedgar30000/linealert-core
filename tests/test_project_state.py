from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_STATE = PROJECT_ROOT / ".project" / "active-work.json"
PROJECT_GUIDANCE = PROJECT_ROOT / ".project" / "README.md"
ROOT_README = PROJECT_ROOT / "README.md"
LINEAGE_GUIDANCE = PROJECT_ROOT / "docs" / "repository-lineage.md"


def load_project_state() -> dict[str, Any]:
    value = json.loads(PROJECT_STATE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_state_snapshot_resolves_streaming_workstream_from_live_main() -> None:
    state = load_project_state()

    assert state["schema_version"] == "project.active-work.v1"
    assert state["repository"]["full_name"] == "anthonyedgar30000/linealert-core"
    assert state["repository"]["role"] == "authoritative_linealert_implementation"
    assert state["state_model"]["record_type"] == "repository_coordination_snapshot"
    assert state["state_model"]["current_reality_source"] == "live_github"
    assert "supersedes cached status" in state["state_model"]["semantics"]

    baseline = state["trusted_baseline"]
    assert baseline["branch"] == "main"
    assert baseline["commit"] == "50985af78df9ee4a352fcfced84ac2703aa98ba0"
    assert baseline["commit_role"] == "verified_main_head_at_streaming_workstream_start"
    assert baseline["last_completed_increment"] == {
        "pull_request": 14,
        "title": "Release project state after PR 13",
        "merge_commit": "50985af78df9ee4a352fcfced84ac2703aa98ba0",
        "implementation_status": "merged",
        "review_status": "merged_with_zero_submitted_reviews",
        "owner_merge_action_observed": True,
    }


def test_streaming_workstream_owns_one_bounded_branch_and_file_set() -> None:
    state = load_project_state()
    assert len(state["workstreams"]) == 1

    workstream = state["workstreams"][0]
    assert workstream["workstream_id"] == "lab-streaming-ingestion-v0.1"
    assert workstream["branch"] == "agent/lab-streaming-ingestion-v0.1"
    assert workstream["pull_request"] == 16
    assert workstream["status"] == (
        "draft_pr_open_requires_exact_head_ci_review_and_control"
    )

    permitted = workstream["permitted_paths"]
    assert len(permitted) == len(set(permitted))
    assert set(permitted) == {
        ".project/active-work.json",
        "docs/streaming_ingestion.md",
        "src/linealert_core/__init__.py",
        "src/linealert_core/simulator.py",
        "src/linealert_core/streaming.py",
        "tests/test_project_state.py",
        "tests/test_streaming.py",
    }
    assert state["tracked_pull_requests"] == [
        {
            "pull_request": 16,
            "title": "Add bounded lab streaming ingestion",
            "state_resolution": "live_github_required",
            "required_state": (
                "draft_until_exact_head_ci_review_and_repository_control_pass"
            ),
        }
    ]


def test_streaming_scope_preserves_existing_reasoning_and_control_boundaries() -> None:
    workstream = load_project_state()["workstreams"][0]
    protected = set(workstream["protected_paths"])
    capabilities = workstream["capability_boundary"]
    equipment = workstream["equipment_scope"]

    assert {
        ".github/workflows/**",
        "README.md",
        "docs/repository-lineage.md",
        "examples/**",
        "adapters/**",
        "deployment/**",
        "src/linealert_core/events.py",
        "src/linealert_core/pipeline.py",
        "src/linealert_core/timing.py",
        "src/linealert_core/baseline.py",
        "src/linealert_core/diagnostic_projection.py",
    }.issubset(protected)
    assert capabilities["pull_request_merge"] is False
    assert capabilities["runtime_code_changes"] is True
    assert capabilities["runtime_change_scope"] == (
        "read-only in-process lab streaming boundary only"
    )
    assert capabilities["deterministic_lab_simulator"] is True
    assert capabilities["external_telemetry_connector"] is False
    assert capabilities["network_listener"] is False
    assert capabilities["persistence_changes"] is False
    assert capabilities["baseline_logic_changes"] is False
    assert capabilities["diagnostic_rule_changes"] is False
    assert capabilities["deployment_mutation"] is False
    assert capabilities["equipment_control"] is False
    assert capabilities["credential_use"] is False
    assert equipment["physical_equipment_connection"] is False
    assert equipment["production_connection"] is False
    assert equipment["control_path"] is False


def test_pr12_pr13_and_pr14_governance_incidents_remain_distinct() -> None:
    state = load_project_state()
    incidents = {
        incident["incident_id"]: incident for incident in state["governance_incidents"]
    }

    assert set(incidents) == {
        "pr12-blocked-merge-2026-07-22",
        "pr13-zero-review-merge-2026-07-22",
        "pr14-zero-review-merge-2026-07-23",
    }
    assert incidents["pr12-blocked-merge-2026-07-22"]["pull_request"] == 12
    assert incidents["pr13-zero-review-merge-2026-07-22"]["pull_request"] == 13

    pr14 = incidents["pr14-zero-review-merge-2026-07-23"]
    assert pr14["pull_request"] == 14
    assert pr14["observed_state"] == "merged"
    assert pr14["merge_commit"] == "50985af78df9ee4a352fcfced84ac2703aa98ba0"
    assert pr14["review_evidence"] == "Live GitHub returned zero submitted reviews."
    assert "not satisfied" in pr14["interpretation"]
    assert state["deployment_state"]["status"] == "not_deployed"


def test_main_review_gate_remains_a_real_pre_merge_requirement() -> None:
    control = load_project_state()["repository_controls"]["main_review_gate"]

    assert control["observed_effect_at_pr14_merge"] == "zero_review_merge_permitted"
    assert control["target_required_approving_reviews"] == 1
    assert control["target_prevent_owner_bypass"] is True
    assert control["enforcement_status"] == "configuration_required"
    assert "one approval" in control["next_gate"]
    assert "preventing owner bypass" in control["next_gate"]


def test_project_lookup_requires_repository_resolution() -> None:
    guidance = PROJECT_GUIDANCE.read_text(encoding="utf-8")

    assert "## Repository resolution gate" in guidance
    assert "exact `owner/repository` target" in guidance
    assert "stop without drawing ownership or project-state conclusions" in guidance
    assert "authoritative only for the resolved repository" in guidance
    assert "A correctly executed lookup against the wrong repository" in guidance


def test_lineage_has_one_authoritative_repo_and_live_archaeology_inventory() -> None:
    lineage = load_project_state()["repository_lineage"]

    assert [item["repository"] for item in lineage["authoritative"]] == [
        "anthonyedgar30000/linealert-core"
    ]

    archaeology = {item["repository"]: item for item in lineage["design_archaeology"]}
    assert set(archaeology) == {
        "anthonyedgar30000/LineAlertDemo",
        "anthonyedgar30000/linealert-analysis-engine",
        "anthonyedgar30000/HelixMemoryService",
    }
    assert archaeology["anthonyedgar30000/LineAlertDemo"]["open_pull_requests"] == [
        2,
        3,
    ]
    assert archaeology["anthonyedgar30000/linealert-analysis-engine"][
        "open_pull_requests"
    ] == [1]
    assert "not current LineAlert persistence" in archaeology[
        "anthonyedgar30000/HelixMemoryService"
    ]["disposition"]


def test_root_readme_and_lineage_guidance_agree() -> None:
    readme = " ".join(ROOT_README.read_text(encoding="utf-8").split())
    lineage = LINEAGE_GUIDANCE.read_text(encoding="utf-8")

    assert "`linealert-core`**: authoritative current LineAlert implementation" in readme
    assert "`ContextOS`**: separate execution-containment" in readme
    assert "`HelixMemoryService`**: early memory-service prototype" in readme
    assert "not current LineAlert persistence, retrieval, or lifecycle-system authority" in readme
    assert "**Assess replay timing against governed baselines**" in lineage
    assert "must not be merged into the current lineage" in lineage
    assert "merged_implementation != governance_gate_satisfied" in lineage
    assert "green_ci != authorized_merge" in lineage
    assert "historical_pattern != current_root_cause" in lineage
    assert "successful_test != safe_production_change" in lineage
