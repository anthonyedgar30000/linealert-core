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


def test_state_snapshot_resolves_current_reality_from_live_github() -> None:
    state = load_project_state()

    assert state["schema_version"] == "project.active-work.v1"
    assert state["repository"]["full_name"] == "anthonyedgar30000/linealert-core"
    assert state["repository"]["role"] == "authoritative_linealert_implementation"
    assert state["state_model"]["record_type"] == "repository_coordination_snapshot"
    assert state["state_model"]["current_reality_source"] == "live_github"
    assert "supersedes cached status" in state["state_model"]["semantics"]

    baseline = state["trusted_baseline"]
    assert baseline["branch"] == "main"
    assert baseline["commit"] == "48d0a45875bd3aa6c87b51383d6b05e9e0e3fce1"
    assert baseline["commit_role"] == "verified_main_head_at_reconciliation_start"
    assert baseline["last_completed_increment"] == {
        "pull_request": 13,
        "title": "Reconcile project state after blocked PR 12 merge",
        "merge_commit": "48d0a45875bd3aa6c87b51383d6b05e9e0e3fce1",
        "implementation_status": "merged",
        "review_status": "merged_with_zero_submitted_reviews",
        "owner_merge_action_observed": True,
    }


def test_reconciliation_ownership_is_live_resolved_and_self_releasing() -> None:
    state = load_project_state()
    assert len(state["workstreams"]) == 1

    workstream = state["workstreams"][0]
    assert workstream["workstream_id"] == "post-pr13-state-release-v0.1"
    assert workstream["branch"] == "chore/reconcile-state-after-pr13"
    assert workstream["pull_request"] == 14
    assert workstream["status_resolution"] == "resolve_from_live_pull_request"
    assert workstream["lifecycle_by_live_pr_state"] == {
        "open": "active_bounded_state_reconciliation",
        "merged": "completed_and_ownership_released",
        "closed_unmerged": "closed_and_ownership_released",
    }

    assert state["tracked_pull_requests"] == [
        {
            "pull_request": 14,
            "title": "Release project state after PR 13",
            "state_resolution": "live_github_required",
            "ownership_resolution": {
                "open": "active",
                "merged": "released",
                "closed_unmerged": "released",
            },
        }
    ]
    assert "known_open_pull_requests" not in state


def test_reconciliation_scope_protects_all_non_state_paths() -> None:
    workstream = load_project_state()["workstreams"][0]
    permitted = set(workstream["permitted_paths"])
    protected = set(workstream["protected_paths"])
    capabilities = workstream["capability_boundary"]

    assert permitted == {
        ".project/active-work.json",
        "tests/test_project_state.py",
    }
    assert len(permitted) == len(workstream["permitted_paths"])
    assert {
        ".github/workflows/**",
        "README.md",
        "docs/**",
        "src/**",
        "examples/**",
        "adapters/**",
        "deployment/**",
    }.issubset(protected)
    assert capabilities["pull_request_merge"] is False
    assert capabilities["runtime_code_changes"] is False
    assert capabilities["documentation_changes"] is False
    assert capabilities["baseline_logic_changes"] is False
    assert capabilities["replay_baseline_logic_changes"] is False
    assert capabilities["telemetry_adapter_implementation"] is False
    assert capabilities["diagnostic_rule_changes"] is False
    assert capabilities["workflow_changes"] is False
    assert capabilities["deployment_mutation"] is False
    assert capabilities["equipment_control"] is False
    assert capabilities["credential_use"] is False


def test_pr12_and_pr13_governance_incidents_remain_distinct() -> None:
    state = load_project_state()
    incidents = {
        incident["incident_id"]: incident for incident in state["governance_incidents"]
    }

    assert set(incidents) == {
        "pr12-blocked-merge-2026-07-22",
        "pr13-zero-review-merge-2026-07-22",
    }
    assert incidents["pr12-blocked-merge-2026-07-22"]["pull_request"] == 12

    pr13 = incidents["pr13-zero-review-merge-2026-07-22"]
    assert pr13["pull_request"] == 13
    assert pr13["observed_state"] == "merged"
    assert pr13["merge_commit"] == "48d0a45875bd3aa6c87b51383d6b05e9e0e3fce1"
    assert pr13["review_evidence"] == "Live GitHub returned zero submitted reviews."
    assert "not independent review" in pr13["interpretation"]
    assert state["deployment_state"]["status"] == "not_deployed"


def test_main_review_gate_records_required_enforcement() -> None:
    control = load_project_state()["repository_controls"]["main_review_gate"]

    assert control["observed_effect_at_pr13_merge"] == "zero_review_merge_permitted"
    assert control["target_required_approving_reviews"] == 1
    assert control["target_prevent_owner_bypass"] is True
    assert control["enforcement_status"] == "configuration_required"
    assert "one approval" in control["next_gate"]
    assert "preventing bypass" in control["next_gate"]


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
