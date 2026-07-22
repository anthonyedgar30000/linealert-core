from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_STATE = PROJECT_ROOT / ".project" / "active-work.json"
PROJECT_GUIDANCE = PROJECT_ROOT / ".project" / "README.md"
LINEAGE_GUIDANCE = PROJECT_ROOT / "docs" / "repository-lineage.md"


def load_project_state() -> dict[str, Any]:
    value = json.loads(PROJECT_STATE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_reconciled_state_resolves_authoritative_repository() -> None:
    state = load_project_state()

    assert state["schema_version"] == "project.active-work.v1"
    assert state["repository"]["full_name"] == "anthonyedgar30000/linealert-core"
    assert state["repository"]["role"] == "authoritative_linealert_implementation"
    assert state["trusted_baseline"]["branch"] == "main"
    assert state["workstreams"] == []
    assert state["known_open_pull_requests"] == []


def test_reconciled_baseline_records_pr9_merge() -> None:
    state = load_project_state()
    baseline = state["trusted_baseline"]
    completed = baseline["last_completed_increment"]

    assert baseline["commit"] == "fa7ad9c09b99a594108a41bb6d09471fbd1a0dc6"
    assert completed == {
        "pull_request": 9,
        "title": "Add governed baseline resolution and drift assessment",
        "merge_commit": "fa7ad9c09b99a594108a41bb6d09471fbd1a0dc6",
    }
    assert state["deployment_state"]["status"] == "not_deployed"


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
    assert "Do not merge or copy wholesale" in archaeology[
        "anthonyedgar30000/LineAlertDemo"
    ]["disposition"]


def test_lineage_guidance_preserves_current_authority_boundaries() -> None:
    guidance = LINEAGE_GUIDANCE.read_text(encoding="utf-8")

    assert "`anthonyedgar30000/linealert-core` is the authoritative implementation" in guidance
    assert "Open PR #2 and PR #3 are non-current prototype work" in guidance
    assert "must not be merged" in guidance
    assert "historical_pattern != current_root_cause" in guidance
    assert "successful_test != safe_production_change" in guidance
