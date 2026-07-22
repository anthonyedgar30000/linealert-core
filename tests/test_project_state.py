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


def test_active_work_resolves_authoritative_repository_and_one_owned_branch() -> None:
    state = load_project_state()

    assert state["schema_version"] == "project.active-work.v1"
    assert state["repository"]["full_name"] == "anthonyedgar30000/linealert-core"
    assert state["repository"]["role"] == "authoritative_linealert_implementation"
    assert state["trusted_baseline"]["branch"] == "main"
    assert len(state["workstreams"]) == 1

    workstream = state["workstreams"][0]
    assert workstream["workstream_id"] == "project-reality-control-v0.1"
    assert workstream["branch"] == "agent/project-reality-control"
    assert workstream["write_owner"]


def test_workstream_scope_is_bounded_and_protects_runtime_paths() -> None:
    state = load_project_state()
    workstream = state["workstreams"][0]
    permitted = set(workstream["permitted_paths"])
    protected = set(workstream["protected_paths"])
    capabilities = workstream["capability_boundary"]

    assert permitted == {
        ".project/README.md",
        ".project/active-work.json",
        "README.md",
        "docs/repository-lineage.md",
        "tests/test_project_state.py",
    }
    assert ".github/workflows/**" in protected
    assert "src/**" in protected
    assert "adapters/**" in protected
    assert "deployment/**" in protected
    assert capabilities["pull_request_merge"] is False
    assert capabilities["runtime_code_changes"] is False
    assert capabilities["telemetry_adapter_implementation"] is False
    assert capabilities["diagnostic_rule_changes"] is False
    assert capabilities["deployment_mutation"] is False
    assert capabilities["equipment_control"] is False
    assert capabilities["credential_use"] is False


def test_permitted_paths_are_unique() -> None:
    state = load_project_state()
    permitted = state["workstreams"][0]["permitted_paths"]

    assert len(permitted) == len(set(permitted))


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
    readme = ROOT_README.read_text(encoding="utf-8")

    assert "**`linealert-core`**: authoritative current LineAlert implementation" in readme
    assert "**`ContextOS`**: separate execution-containment" in readme
    assert "**`HelixMemoryService`**: early memory-service prototype" in readme
    assert "it is not\n  the current LineAlert persistence" in readme
