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


def test_active_work_resolves_authoritative_repository_and_owned_branch() -> None:
    state = load_project_state()

    assert state["schema_version"] == "project.active-work.v1"
    assert state["repository"]["full_name"] == "anthonyedgar30000/linealert-core"
    assert state["repository"]["role"] == "authoritative_linealert_implementation"
    assert state["trusted_baseline"]["branch"] == "main"
    assert state["trusted_baseline"]["commit"] == (
        "f991dfa72aa2967e54b8f69c18c2c91181c2e8cb"
    )
    assert state["trusted_baseline"]["last_completed_increment"] == {
        "pull_request": 10,
        "title": "Reconcile project state after PR 9",
        "merge_commit": "f991dfa72aa2967e54b8f69c18c2c91181c2e8cb",
    }
    assert len(state["workstreams"]) == 1

    workstream = state["workstreams"][0]
    assert workstream["workstream_id"] == "replay-baseline-assessment-v0.1"
    assert workstream["branch"] == "feature/replay-baseline-assessment"
    assert workstream["pull_request"] == 12
    assert workstream["write_owner"]


def test_replay_baseline_workstream_scope_and_authority_are_bounded() -> None:
    state = load_project_state()
    workstream = state["workstreams"][0]
    permitted = set(workstream["permitted_paths"])
    capabilities = workstream["capability_boundary"]

    assert permitted == {
        ".project/active-work.json",
        "docs/replay_baseline_assessment.md",
        "examples/labeler_timing_baseline_contexts.json",
        "src/linealert_core/__init__.py",
        "src/linealert_core/baseline_replay.py",
        "src/linealert_core/cli.py",
        "tests/test_baseline_replay.py",
        "tests/test_project_state.py",
    }
    assert capabilities["replay_timing_baseline_assessment"] is True
    assert capabilities["baseline_registry_loading"] is True
    assert capabilities["timing_context_loading"] is True
    assert capabilities["optional_cli_reporting"] is True
    assert capabilities["timing_rule_changes"] is False
    assert capabilities["diagnostic_rule_changes"] is False
    assert capabilities["automatic_rebaselining"] is False
    assert capabilities["live_telemetry_integration"] is False
    assert capabilities["deployment_mutation"] is False
    assert capabilities["equipment_control"] is False
    assert capabilities["credential_use"] is False
    assert len(permitted) == len(workstream["permitted_paths"])
    assert state["deployment_state"]["status"] == "not_deployed"
    assert state["known_open_pull_requests"] == [
        {
            "pull_request": 11,
            "title": "Reconcile LineAlert lineage boundaries",
            "status": "draft_parallel_owner_of_overlapping_project_state_paths",
            "action": (
                "Resolve PR #11 before PR #12 proceeds because it owns "
                ".project/active-work.json and tests/test_project_state.py."
            ),
        },
        {
            "pull_request": 12,
            "title": "Assess replay timing against governed baselines",
            "status": "draft_blocked_by_pr11_scope_collision",
            "action": (
                "Do not merge. Rebase and reconcile ownership only after PR #11 "
                "resolves."
            ),
        },
    ]


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
