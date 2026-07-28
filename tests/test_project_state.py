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
PR17_MERGE = "a094f0812ad85bfbcfe3c90c4cbc1d85547be7cd"


def load_project_state() -> dict[str, Any]:
    value = json.loads(PROJECT_STATE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_state_snapshot_advances_to_pr17_main() -> None:
    state = load_project_state()

    assert state["schema_version"] == "project.active-work.v1"
    assert state["repository"]["full_name"] == "anthonyedgar30000/linealert-core"
    assert state["repository"]["role"] == "authoritative_linealert_implementation"
    assert state["state_model"]["record_type"] == "repository_coordination_snapshot"
    assert state["state_model"]["captured_from_main"] == PR17_MERGE
    assert state["state_model"]["current_reality_source"] == "live_github"
    assert "supersedes cached status" in state["state_model"]["semantics"]

    baseline = state["trusted_baseline"]
    assert baseline["branch"] == "main"
    assert baseline["commit"] == PR17_MERGE
    assert baseline["commit_role"] == "verified_main_head_after_pr17_merge"
    assert baseline["last_completed_increment"] == {
        "pull_request": 17,
        "title": "Reconcile project state after PR 16",
        "merge_commit": PR17_MERGE,
        "increment_type": "state_only_reconciliation",
        "implementation_status": "merged",
        "review_status": "merged_with_zero_submitted_reviews",
        "governance_gate_status": "recorded_pre_merge_gate_not_satisfied",
    }
    assert baseline["last_functional_increment"] == {
        "pull_request": 16,
        "title": "Add bounded lab streaming ingestion",
        "merge_commit": PR16_MERGE,
        "exact_head_ci_status": "success",
        "exact_head_ci_run": 30385722716,
        "deployment_status": "not_deployed",
    }


def test_corrective_hardening_owns_one_live_resolved_workstream() -> None:
    state = load_project_state()
    assert len(state["workstreams"]) == 1

    workstream = state["workstreams"][0]
    assert workstream["workstream_id"] == "streaming-evidence-hardening-v0.2"
    assert workstream["branch"] == "agent/harden-streaming-evidence-v0.2"
    assert workstream["pull_request"] == 20
    assert workstream["classification"] == (
        "corrective_hardening_of_existing_public_code"
    )
    assert workstream["status_resolution"] == "resolve_from_live_pull_request"
    assert workstream["lifecycle_by_live_pr_state"] == {
        "open": "active_bounded_corrective_hardening",
        "merged": "completed_and_ownership_released",
        "closed_unmerged": "closed_and_ownership_released",
    }

    permitted = workstream["permitted_paths"]
    assert len(permitted) == len(set(permitted))
    assert set(permitted) == {
        ".project/active-work.json",
        "docs/streaming_ingestion.md",
        "src/linealert_core/streaming.py",
        "tests/test_project_state.py",
        "tests/test_streaming.py",
    }
    assert state["tracked_pull_requests"] == [
        {
            "pull_request": 20,
            "title": "Harden streaming evidence after PR 17",
            "state_resolution": "live_github_required",
            "ownership_resolution": {
                "open": "active",
                "merged": "released",
                "closed_unmerged": "released",
            },
            "required_state": (
                "draft_until_exact_head_ci_visibility_review_and_"
                "repository_controls_pass"
            ),
        }
    ]


def test_corrective_scope_preserves_runtime_and_control_boundaries() -> None:
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
        "src/linealert_core/__init__.py",
        "src/linealert_core/events.py",
        "src/linealert_core/pipeline.py",
        "src/linealert_core/simulator.py",
        "src/linealert_core/timing.py",
        "src/linealert_core/baseline.py",
        "src/linealert_core/diagnostic_projection.py",
    }.issubset(protected)
    assert capabilities["pull_request_merge"] is False
    assert capabilities["runtime_code_changes"] is True
    assert capabilities["runtime_change_scope"] == (
        "corrective hardening of existing read-only in-process streaming evidence"
    )
    assert capabilities["new_proprietary_increment"] is False
    assert capabilities["external_telemetry_connector"] is False
    assert capabilities["network_listener"] is False
    assert capabilities["persistence_changes"] is False
    assert capabilities["baseline_logic_changes"] is False
    assert capabilities["diagnostic_rule_changes"] is False
    assert capabilities["workflow_changes"] is False
    assert capabilities["deployment_mutation"] is False
    assert capabilities["equipment_control"] is False
    assert capabilities["credential_use"] is False
    assert equipment["physical_equipment_connection"] is False
    assert equipment["production_connection"] is False
    assert equipment["control_path"] is False


def test_two_streaming_findings_remain_explicit_until_reviewed() -> None:
    findings = {
        finding["finding_id"]: finding
        for finding in load_project_state()["workstreams"][0]["review_findings"]
    }

    assert set(findings) == {
        "transport-attributes-not-deeply-immutable",
        "session-transition-committed-before-core-acceptance",
    }
    for finding in findings.values():
        assert finding["source"] == "post-PR16 author-side read-only inspection"
        assert finding["disposition"] == (
            "remediation_implemented_on_pr20_requires_ci_and_review"
        )


def test_governance_incidents_remain_distinct_through_pr17() -> None:
    state = load_project_state()
    incidents = {
        incident["incident_id"]: incident for incident in state["governance_incidents"]
    }

    assert set(incidents) == {
        "pr12-blocked-merge-2026-07-22",
        "pr13-zero-review-merge-2026-07-22",
        "pr14-zero-review-merge-2026-07-23",
        "pr16-zero-review-gate-bypass-2026-07-28",
        "pr17-zero-review-gate-bypass-2026-07-28",
    }
    assert incidents["pr12-blocked-merge-2026-07-22"]["pull_request"] == 12
    assert incidents["pr13-zero-review-merge-2026-07-22"]["pull_request"] == 13
    assert incidents["pr14-zero-review-merge-2026-07-23"]["pull_request"] == 14

    pr16 = incidents["pr16-zero-review-gate-bypass-2026-07-28"]
    assert pr16["pull_request"] == 16
    assert pr16["merge_commit"] == PR16_MERGE
    assert PR16_HEAD in pr16["exact_head_ci_evidence"]
    assert "30385722716" in pr16["exact_head_ci_evidence"]

    pr17 = incidents["pr17-zero-review-gate-bypass-2026-07-28"]
    assert pr17["pull_request"] == 17
    assert pr17["observed_state"] == "merged"
    assert pr17["merge_commit"] == PR17_MERGE
    assert pr17["review_evidence"] == "Live GitHub returned zero submitted reviews."
    assert "not satisfied" in pr17["interpretation"]


def test_repository_controls_preserve_review_and_visibility_gates() -> None:
    controls = load_project_state()["repository_controls"]

    review = controls["main_review_gate"]
    assert review["tracking_issue"] == 15
    assert review["observed_effect_at_pr17_merge"] == "zero_review_merge_permitted"
    assert review["target_required_approving_reviews"] == 1
    assert review["target_dismiss_stale_approvals"] is True
    assert review["target_prevent_owner_bypass"] is True
    assert review["enforcement_status"] == "configuration_required_and_unverified"
    assert "stale-approval dismissal" in review["next_gate"]
    assert "no owner bypass" in review["next_gate"]

    visibility = controls["repository_visibility"]
    assert visibility["observed_visibility"] == "public"
    assert visibility["target_visibility"] == "private"
    assert visibility["status"] == "configuration_required"
    assert "canonical repository plan" in visibility["evidence"]
    assert "PR #20" in visibility["next_gate"]


def test_deployment_and_equipment_reality_remain_bounded() -> None:
    deployment = load_project_state()["deployment_state"]

    assert deployment["status"] == "not_deployed"
    assert "physical-equipment connection" in deployment["evidence"]
    assert "network listener" in deployment["evidence"]
    assert "equipment-control path" in deployment["evidence"]


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
