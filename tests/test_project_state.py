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


def test_active_work_resolves_authoritative_repository_and_branch() -> None:
    state = load_project_state()

    assert state["schema_version"] == "project.active-work.v1"
    assert state["repository"]["full_name"] == "anthonyedgar30000/linealert-core"
    assert state["repository"]["role"] == "authoritative_linealert_implementation"
    assert state["trusted_baseline"]["branch"] == "main"
    assert len(state["workstreams"]) == 1

    workstream = state["workstreams"][0]
    assert workstream["workstream_id"] == "lineage-boundary-reconciliation-v0.1"
    assert workstream["branch"] == "agent/reconcile-lineage-boundaries"
    assert workstream["pull_request"] == 11
    assert state["known_open_pull_requests"][0]["pull_request"] == 11


def test_trusted_baseline_records_pr10_merge() -> None:
    baseline = load_project_state()["trusted_baseline"]

    assert baseline["commit"] == "f991dfa72aa2967e54b8f69c18c2c91181c2e8cb"
    assert baseline["last_completed_increment"] == {
        "pull_request": 10,
        "title": "Reconcile project state after PR 9",
        "merge_commit": "f991dfa72aa2967e54b8f69c18c2c91181c2e8cb",
    }


def test_workstream_scope_is_bounded_and_protects_implementation() -> None:
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
    assert "src/**" in protected
    assert "examples/**" in protected
    assert "adapters/**" in protected
    assert "deployment/**" in protected
    assert capabilities["pull_request_merge"] is False
    assert capabilities["runtime_code_changes"] is False
    assert capabilities["baseline_logic_changes"] is False
    assert capabilities["telemetry_adapter_implementation"] is False
    assert capabilities["diagnostic_rule_changes"] is False
    assert capabilities["deployment_mutation"] is False
    assert capabilities["equipment_control"] is False
    assert capabilities["credential_use"] is False
    assert len(workstream["permitted_paths"]) == len(set(workstream["permitted_paths"]))


def test_project_lookup_requires_repository_resolution() -> None:
    guidance = PROJECT_GUIDANCE.read_text(encoding="utf-8")

    assert "## Repository resolution gate" in guidance
    assert "exact `owner/repository` target" in guidance
    assert "stop without drawing ownership or project-state conclusions" in guidance
    assert "authoritative only for the resolved repository" in guidance
    assert "A correctly executed lookup against the wrong repository" in guidance


def test_lineage_has_one_authoritative_repo_and_formal_archaeology() -> None:
    state = load_project_state()
    lineage = state["repository_lineage"]

    assert [item["repository"] for item in lineage["authoritative"]] == [
        "anthonyedgar30000/linealert-core"
    ]

    archaeology = {item["repository"]: item for item in lineage["design_archaeology"]}
    assert set(archaeology) == {
        "anthonyedgar30000/LineAlertDemo",
        "anthonyedgar30000/linealert-analysis-engine",
        "anthonyedgar30000/HelixMemoryService",
    }
    assert archaeology["anthonyedgar30000/LineAlertDemo"]["open_pull_requests"] == [2, 3]
    assert archaeology["anthonyedgar30000/linealert-analysis-engine"][
        "open_pull_requests"
    ] == [1]
    assert "Do not merge or copy wholesale" in archaeology[
        "anthonyedgar30000/LineAlertDemo"
    ]["disposition"]
    assert "not current LineAlert persistence" in archaeology[
        "anthonyedgar30000/HelixMemoryService"
    ]["disposition"]


def test_lineage_guidance_preserves_current_authority_boundaries() -> None:
    guidance = LINEAGE_GUIDANCE.read_text(encoding="utf-8")

    assert "`anthonyedgar30000/linealert-core` is the authoritative implementation" in guidance
    assert "Open PR #2 and PR #3 are non-current prototype work" in guidance
    assert "Open PR #1, **Implement Phase 1 backend analysis**, is non-current" in guidance
    assert "must not be merged" in guidance
    assert "historical_pattern != current_root_cause" in guidance
    assert "successful_test != safe_production_change" in guidance


def test_root_readme_agrees_with_repository_lineage() -> None:
    readme = " ".join(ROOT_README.read_text(encoding="utf-8").split())

    assert "`linealert-core`**: authoritative current LineAlert implementation" in readme
    assert "`ContextOS`**: separate execution-containment" in readme
    assert "`HelixMemoryService`**: early memory-service prototype" in readme
    assert "not the current LineAlert persistence, retrieval, or lifecycle-system authority" in readme
