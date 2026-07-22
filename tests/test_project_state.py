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


def test_active_work_resolves_current_main_and_owned_reconciliation() -> None:
    state = load_project_state()

    assert state["schema_version"] == "project.active-work.v1"
    assert state["repository"]["full_name"] == "anthonyedgar30000/linealert-core"
    assert state["repository"]["role"] == "authoritative_linealert_implementation"

    baseline = state["trusted_baseline"]
    assert baseline["branch"] == "main"
    assert baseline["commit"] == "a1812ff69ef6cb05031bced9f4dc7577c6ae8d2a"
    assert baseline["last_completed_increment"] == {
        "pull_request": 12,
        "title": "Assess replay timing against governed baselines",
        "merge_commit": "a1812ff69ef6cb05031bced9f4dc7577c6ae8d2a",
        "implementation_status": "merged",
        "governance_status": "merged_despite_recorded_blocking_scope_collision",
    }

    assert len(state["workstreams"]) == 1
    workstream = state["workstreams"][0]
    assert workstream["workstream_id"] == "post-pr12-reality-reconciliation-v0.1"
    assert workstream["branch"] == "chore/reconcile-state-after-pr12"
    assert workstream["pull_request"] == 13
    assert workstream["status"] == "implemented_on_branch_requires_live_ci_lookup"
    assert state["known_open_pull_requests"] == [
        {
            "pull_request": 13,
            "title": "Reconcile project state after blocked PR 12 merge",
            "status": "draft_requires_live_exact_head_ci_and_review",
            "action": (
                "Keep draft. Resolve CI from live GitHub for the exact current head, "
                "complete independent read-only review, and obtain explicit human "
                "approval before merge."
            ),
        }
    ]


def test_reconciliation_scope_protects_merged_implementation() -> None:
    workstream = load_project_state()["workstreams"][0]
    permitted = set(workstream["permitted_paths"])
    protected = set(workstream["protected_paths"])
    capabilities = workstream["capability_boundary"]

    assert permitted == {
        ".project/active-work.json",
        "README.md",
        "docs/repository-lineage.md",
        "tests/test_project_state.py",
    }
    assert len(permitted) == len(workstream["permitted_paths"])
    assert ".github/workflows/**" in protected
    assert "src/**" in protected
    assert "examples/**" in protected
    assert "adapters/**" in protected
    assert "deployment/**" in protected
    assert capabilities["pull_request_merge"] is False
    assert capabilities["runtime_code_changes"] is False
    assert capabilities["baseline_logic_changes"] is False
    assert capabilities["replay_baseline_logic_changes"] is False
    assert capabilities["telemetry_adapter_implementation"] is False
    assert capabilities["diagnostic_rule_changes"] is False
    assert capabilities["deployment_mutation"] is False
    assert capabilities["equipment_control"] is False
    assert capabilities["credential_use"] is False


def test_pr12_merge_and_governance_violation_are_both_preserved() -> None:
    state = load_project_state()
    incidents = state["governance_incidents"]

    assert len(incidents) == 1
    incident = incidents[0]
    assert incident["incident_id"] == "pr12-blocked-merge-2026-07-22"
    assert incident["pull_request"] == 12
    assert incident["observed_state"] == "merged"
    assert incident["recorded_pre_merge_state"] == (
        "blocked_by_overlapping_project_state_scope_pr11"
    )
    assert "Passing CI did not satisfy" in incident["interpretation"]
    assert state["deployment_state"]["status"] == "not_deployed"


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
