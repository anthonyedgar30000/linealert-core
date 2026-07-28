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
PR16_HEAD = "3881f6962bc6d530f5e0cbae30e301b1a0eacbc5"


def load_project_state() -> dict[str, Any]:
    value = json.loads(PROJECT_STATE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_state_snapshot_advances_to_merged_pr16_main() -> None:
    state = load_project_state()

    assert state["schema_version"] == "project.active-work.v1"
    assert state["repository"]["full_name"] == "anthonyedgar30000/linealert-core"
    assert state["repository"]["role"] == "authoritative_linealert_implementation"
    assert state["state_model"]["record_type"] == "repository_coordination_snapshot"
    assert state["state_model"]["captured_from_main"] == PR16_MERGE
    assert state["state_model"]["current_reality_source"] == "live_github"
    assert "supersedes cached status" in state["state_model"]["semantics"]

    baseline = state["trusted_baseline"]
    assert baseline["branch"] == "main"
    assert baseline["commit"] == PR16_MERGE
    assert baseline["commit_role"] == "verified_main_head_after_pr16_merge"
    assert baseline["last_completed_increment"] == {
        "pull_request": 16,
        "title": "Add bounded lab streaming ingestion",
        "merge_commit": PR16_MERGE,
        "implementation_status": "merged",
        "exact_head_ci_status": "success",
        "exact_head_ci_run": 30385722716,
        "review_status": "merged_with_zero_submitted_reviews",
        "governance_gate_status": "recorded_pre_merge_gate_not_satisfied",
    }


def test_merged_streaming_workstream_releases_branch_ownership() -> None:
    state = load_project_state()

    assert state["workstreams"] == []
    assert state["tracked_pull_requests"] == []
    assert state["deployment_state"]["status"] == "not_deployed"
    assert "physical-equipment connection" in state["deployment_state"]["evidence"]
    assert "equipment-control path" in state["deployment_state"]["evidence"]


def test_pr16_merge_is_preserved_as_implementation_and_governance_incident() -> None:
    state = load_project_state()
    incidents = {
        incident["incident_id"]: incident for incident in state["governance_incidents"]
    }

    assert {
        "pr12-blocked-merge-2026-07-22",
        "pr13-zero-review-merge-2026-07-22",
        "pr14-zero-review-merge-2026-07-23",
        "pr16-zero-review-gate-bypass-2026-07-28",
    } == set(incidents)

    pr16 = incidents["pr16-zero-review-gate-bypass-2026-07-28"]
    assert pr16["pull_request"] == 16
    assert pr16["observed_state"] == "merged"
    assert pr16["merge_commit"] == PR16_MERGE
    assert PR16_HEAD in pr16["exact_head_ci_evidence"]
    assert "30385722716" in pr16["exact_head_ci_evidence"]
    assert pr16["review_evidence"] == "Live GitHub returned zero submitted reviews."
    assert "did not satisfy" in pr16["interpretation"]
    assert "block the next implementation merge" in pr16["corrective_action"]


def test_repository_controls_record_review_and_visibility_gates() -> None:
    controls = load_project_state()["repository_controls"]

    review = controls["main_review_gate"]
    assert review["observed_effect_at_pr16_merge"] == "zero_review_merge_permitted"
    assert review["target_required_approving_reviews"] == 1
    assert review["target_prevent_owner_bypass"] is True
    assert review["enforcement_status"] == "configuration_required"
    assert "preventing owner bypass" in review["next_gate"]

    visibility = controls["repository_visibility"]
    assert visibility["observed_visibility"] == "public"
    assert visibility["target_visibility"] == "private"
    assert visibility["status"] == "configuration_required"
    assert "canonical repository plan" in visibility["evidence"]
    assert "before adding another proprietary implementation increment" in (
        visibility["next_gate"]
    )


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
