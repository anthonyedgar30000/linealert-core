from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_STATE = PROJECT_ROOT / ".project" / "active-work.json"
PROJECT_GUIDANCE = PROJECT_ROOT / ".project" / "README.md"
ROOT_README = PROJECT_ROOT / "README.md"
LINEAGE_GUIDANCE = PROJECT_ROOT / "docs" / "repository-lineage.md"
TRANSACTION_INVENTORY = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "current-dependency-and-transaction-inventory.md"
)
CI_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
SPEEDWAY_SCOPE = (
    PROJECT_ROOT / "docs" / "architecture" / "speedway-service-workflow-scope-v1.md"
)
SERVICE_CASE_CONTRACT = (
    PROJECT_ROOT / "docs" / "architecture" / "service-case-data-contract-v1.md"
)
SPEEDWAY_WORKSPACE = (
    PROJECT_ROOT / "docs" / "architecture" / "speedway-service-workspace-v1.md"
)
SERVICE_CASE_PERSISTENCE = (
    PROJECT_ROOT / "docs" / "architecture" / "service-case-local-persistence-v1.md"
)
LIVE_EMULATED_HISTORIAN = (
    PROJECT_ROOT / "docs" / "architecture" / "live-emulated-historian-v1.md"
)
REASONING_SSR = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "reasoning-server-rendered-readiness-v1.md"
)

PR37_HEAD = "fc22177e1b855fd6f416f648330cd3416215a96c"
PR37_MERGE = "97256907cd428a8a0ba3dfb7d4020fa19a2485ee"
PR38_HEAD = "0d5d8180a5edffaeca8a9822800d7e729ef96327"
PR38_MERGE = "06f795e760c7ad360bc51e264f8c55238a2a60da"
PR114_MERGE = "4037c2c0bcadce3e3e6e414735c0045b65db6027"
CURRENT_MAIN = "17bc6abbf402a2532b64a58f701f707833b4d671"
CURRENT_TREE = "c813cd5e27ffdf801a2ee5bda572627b75f3fd7b"
PR150_HEAD = "d300af099fe493f5e6c727c66f2f0371d2ccbf86"
PR157_HEAD = "c0c05d414fd007ff7c8f90154fe67eb67531f69f"


def load_project_state() -> dict[str, Any]:
    value = json.loads(PROJECT_STATE.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_state_snapshot_tracks_current_main_and_public_demo() -> None:
    state = load_project_state()
    assert state["schema_version"] == "project.active-work.v1"
    assert state["updated_on"] == "2026-09-28"
    assert state["repository"]["full_name"] == (
        "anthonyedgar30000/linealert-core"
    )
    assert state["state_model"]["captured_from_main"] == CURRENT_MAIN

    policy = state["state_model"]["publication_policy"]
    assert policy["state_only_merge_requires_immediate_self_sync"] is False
    assert policy["publication_pr_self_reference_required"] is False
    assert "substantive external lifecycle" in policy["rule"]
    assert "PR #157 merged the explicit live emulated historian" in (
        policy["current_correction_reason"]
    )
    assert "server-rendered readiness increment" in (
        policy["current_correction_reason"]
    )

    observation = state["live_observation"]
    assert observation["default_branch_head"] == CURRENT_MAIN
    assert observation["default_branch_tree"] == CURRENT_TREE
    assert observation["open_pull_requests_before_branch_creation"] == []
    assert observation["active_sync_pull_request"] is None
    assert observation["open_issues"] == [31]
    assert observation["latest_merged_pull_request"] == {
        "pull_request": 157,
        "title": "Add live emulated historian",
        "source_head": PR157_HEAD,
        "merge_commit": CURRENT_MAIN,
    }
    assert observation["recently_closed_issues"]["23"] == {
        "state": "closed_completed",
        "closed_by_pull_request": 38,
        "reason": "all_four_atomic_ingestion_windows_resolved",
    }
    assert observation["recently_closed_issues"]["111"]["state"] == (
        "closed_completed"
    )
    assert observation["visibility"]["status"] == "verified_public"

    ci = observation["main_ci"]
    assert ci["verification_scope"] == "merged_main_push"
    assert ci["pull_request"] == 157
    assert ci["run_id"] == 36500616625
    assert ci["head_sha"] == CURRENT_MAIN
    assert ci["merge_commit"] == CURRENT_MAIN
    assert ci["conclusion"] == "success"
    assert ci["jobs"] == ["test (3.11)", "test (3.12)", "ui-build"]
    assert ci["checkout_provenance"] == "literal_push_sha"
    assert ci["merge_commit_ci"] == "verified_success"

    pages = observation["public_pages"]
    assert pages["status"] == "observed_deployed_2026_09_28"
    assert pages["workflow_run"] == 36500616599
    assert pages["source_commit"] == CURRENT_MAIN
    assert pages["source_tree"] == CURRENT_TREE
    assert pages["fresh_verification_in_this_sync"] is True
    assert pages["investigation_workspace"].endswith("/investigation/")
    assert "not a production LineAlert runtime" in pages["note"]


def test_pr38_runtime_atomicity_is_preserved_and_bounded() -> None:
    state = load_project_state()
    completed = state["trusted_baseline"]["last_completed_increment"]
    assert completed["pull_request"] == 38
    assert completed["source_head"] == PR38_HEAD
    assert completed["merge_commit"] == PR38_MERGE
    assert completed["pull_request_ci"] == {
        "run_id": 30516440394,
        "conclusion": "success",
        "python_versions": ["3.11", "3.12"],
        "checkout_provenance": "literal_pull_request_head_sha",
        "test_summary": "74_passed_0_xfailed",
    }
    assert completed["submitted_reviews"] == 0
    assert completed["deployment_status"] == "not_deployed"

    runtime = state["trusted_baseline"]["last_merged_runtime_increment"]
    assert runtime["pull_request"] == 38
    assert runtime["source_head"] == PR38_HEAD
    assert runtime["merge_commit"] == PR38_MERGE
    assert runtime["resolved_windows"] == [
        "FW-01_event_identity_commit",
        "FW-02_timing_start_evidence_preservation",
        "FW-03_later_subscriber_rollback",
        "FW-04_diagnostic_derivation_rollback",
    ]
    assert runtime["remaining_windows"] == []
    assert runtime["external_side_effect_rollback"] == "not_claimed"


def test_issue_23_is_closed_with_all_invariants_promoted() -> None:
    issue = load_project_state()["issue_lifecycle"]["23"]
    assert issue["state"] == "closed_completed"
    assert issue["final_remediation"] == "FW-03_and_FW-04_merged_by_pr38"
    assert issue["remaining_scope"] == []
    assert issue["latest_verification"] == {
        "pull_request": 38,
        "ci_run": 30516440394,
        "test_summary": "74_passed_0_xfailed",
        "remaining_xfails": [],
    }
    assert "arbitrary_external_side_effects_are_not_transactional" in (
        issue["limitations"]
    )
    assert "software_atomicity_does_not_establish_equipment_safety" in (
        issue["limitations"]
    )


def test_stage1_authority_and_environment_gates_remain_bounded() -> None:
    state = load_project_state()
    workstream = state["workstreams"][0]
    assert workstream["tracking_issue"] == 31
    assert workstream["state"] == (
        "owner_authorized_waiting_for_azure_environment_and_identity_package"
    )
    assert workstream["authority"] == {
        "owner_stage_1_authority": (
            "granted_for_disposable_non_production_lab"
        ),
        "independent_review_for_bounded_stage_1": (
            "not_required_by_current_owner_risk_decision"
        ),
        "qualified_review_for_later_live_or_production_scope": "required",
        "live_linealert_adapter_authority": "not_granted",
        "physical_equipment_authority": "not_granted",
        "equipment_control_authority": "not_granted",
    }
    assert workstream["blockers"] == [
        "no_azure_management_connection_available_in_current_workspace",
        (
            "disposable_subscription_region_resource_group_cleanup_owner_"
            "and_credential_custodian_not_recorded"
        ),
    ]

    capability = workstream["capability_boundary"]
    assert capability[
        "disposable_stage_1_azure_lab_after_environment_gates"
    ] is True
    for field in {
        "offline_fixture_mapping_after_captured_evidence",
        "linealert_live_opcua_or_mqtt_adapter",
        "public_opcua_exposure",
        "credentials_in_repository",
        "physical_equipment_connection",
        "equipment_control",
    }:
        assert capability[field] is False

    issue_31 = state["issue_lifecycle"]["31"]
    assert issue_31["azure_resources"] == "not_observed"
    assert issue_31["execution_environment"] == (
        "not_available_in_current_workspace"
    )
    assert issue_31["identity_resource_package"] == "not_recorded"
    assert issue_31["live_adapter_authority"] == "not_granted"


def test_pr37_and_pr38_lifecycle_evidence_is_preserved() -> None:
    state = load_project_state()
    previous = state["trusted_baseline"]["last_repository_state_increment"]
    assert previous["pull_request"] == 37
    assert previous["source_head"] == PR37_HEAD
    assert previous["merge_commit"] == PR37_MERGE
    assert previous["pull_request_ci"]["run_id"] == 30509312378
    assert previous["pull_request_ci"]["test_summary"] == (
        "72_passed_2_xfailed"
    )

    incidents = {
        item["id"]: item
        for item in state["governance_incident_history"]["incidents"]
    }
    pr38 = incidents["pr38-runtime-atomicity-merged-2026-07-30"]
    assert pr38["source_head"] == PR38_HEAD
    assert pr38["merge_commit"] == PR38_MERGE
    assert pr38["ci_run"] == 30516440394
    assert pr38["reviews"] == 0
    assert "not_observable" in pr38["classification"]



def test_initial_commercial_scope_is_speedway_service_workflow() -> None:
    state = load_project_state()
    scope = state["product_scope"]

    assert scope["scope_version"] == "speedway_service_workflow_v1"
    assert scope["status"] == "authoritative_initial_commercial_scope"

    user = scope["primary_user"]
    assert user["role"] == "speedway_service_maintenance_technician"
    assert user["organization_context"] == "Speedway"
    assert user["plant_operator_required_as_linealert_user"] is False
    assert user["plant_internal_maintenance_required_as_linealert_user"] is False

    workflow = scope["service_case_workflow"]
    assert workflow[0] == "service_call_received"
    assert "identify_first_detected_departure_if_supported" in workflow
    assert "technician_requests_targeted_plant_context" in workflow
    assert "produce_bounded_service_evidence_package" in workflow

    departure = scope["first_detected_departure"]
    assert departure["requires_retained_evidence"] is True
    assert departure["temporal_precedence_confers_causation"] is False
    assert "root_cause" in departure["not_equivalent_to"]

    plant = scope["plant_context_strategy"]
    assert plant["plant_people_role"] == "external_context_and_evidence_source"
    assert plant["direct_cmms_integration_required_for_v1"] is False
    assert plant["reported_context_default_classification"] == "plant_reported_context"
    assert plant["reported_context_is_verified_source_record"] is False
    for field in {
        "reported_event_time_or_window",
        "entered_at",
        "entered_by",
        "reported_source",
        "original_wording_or_bounded_summary",
        "source_verification_state",
        "asset_or_process_scope",
        "reported_clock_quality",
    }:
        assert field in plant["manual_entry_must_preserve"]

    ui = scope["initial_ui_direction"]
    assert ui["target_primary_surface"] == "Speedway Service Workspace"
    assert ui["current_plant_canvas"] == (
        "legacy_synthetic_demo_not_initial_commercial_target"
    )
    assert ui["customer_facing_operator_workflow"] == "deferred"

    assert "direct_client_cmms_integration" in scope["deferred_from_initial_scope"]
    assert "equipment_control" in scope["deferred_from_initial_scope"]

    boundaries = scope["boundaries"]
    assert "first_detected_departure != root_cause" in boundaries
    assert "plant_reported_context != verified_source_record" in boundaries
    assert "technician_entry != direct_system_observation" in boundaries

    architecture = SPEEDWAY_SCOPE.read_text(encoding="utf-8")
    assert "Speedway service / maintenance technician" in architecture
    assert "plant_reported_context != verified_source_record" in architecture
    assert "Temporal precedence" in architecture


def test_service_case_contract_reality_is_bounded_and_non_authoritative() -> None:
    state = load_project_state()
    contract = state["service_case_contract_reality"]

    assert contract["status"] == "executable_v1_contract_defined"
    assert contract["source_baseline_main"] == CURRENT_MAIN
    assert contract["schema_versions"] == [
        "linealert.service-case.v1",
        "linealert.plant-reported-context.v1",
    ]
    assert contract["objects"] == [
        "ServiceCase",
        "FirstDetectedDeparture",
        "PlantReportedContext",
    ]
    assert contract["direct_source_retrieval_state_available"] is False
    assert contract["manual_plant_context_verification_states"] == [
        "plant_relay_only",
        "technician_viewed_source",
        "technician_retained_copy",
    ]
    assert contract["plant_context_binding_validation"] == [
        "service_case_id_match",
        "asset_id_match",
        "context_id_referenced_by_service_case",
    ]
    assert contract["persistence"] == "local_atomic_json_single_process_v1"
    assert contract["api"] == "loopback_local_service_v1"
    assert contract["speedway_service_workspace_ui"] == "merged_primary_surface"
    assert contract["local_persistence_seed"] == (
        "examples/speedway_service_case_workspace_seed_v1.json"
    )
    assert contract["local_persistence_failure_mode"] == "fail_closed_for_writes"
    assert contract["automatic_first_departure_selection"] == "not_implemented"
    assert contract["reasoning_node_consumption"] == "not_implemented"
    assert contract["direct_cmms_integration"] == "not_implemented"
    assert contract["equipment_control"] == "not_authorized"
    assert "reported_clock_quality" in contract["preserved_time_and_quality"]
    assert "reported_event_time != verified_machine_timestamp" in (
        contract["claim_boundaries"]
    )

    architecture = SERVICE_CASE_CONTRACT.read_text(encoding="utf-8")
    assert "There is intentionally no direct_source_retrieval state" in architecture
    assert "reported_clock_quality" in architecture
    assert "first_detected_departure != root_cause" in architecture
    assert "service-case-local-persistence-v1.md" in architecture


def test_speedway_service_workspace_reality_is_primary_and_bounded() -> None:
    state = load_project_state()
    demo = state["current_demo_reality"]

    assert demo["primary_surface"] == "Speedway Service Workspace"
    assert "Legacy Plant Canvas" in demo["supporting_surfaces"]
    assert "Reasoning Inputs" in demo["supporting_surfaces"]
    assert "Machine Health / Evidence" in demo["supporting_surfaces"]

    workspace = demo["speedway_service_workspace"]
    assert workspace["state"] == "merged_primary_surface_with_local_persistence"
    assert workspace["route"] == "/"
    assert workspace["legacy_operator_demo_route"] == "/plant-canvas"
    assert workspace["plant_context_entry"] == "local_persistent_v1_merged"
    assert workspace["persistence_status"] == "local_atomic_json_single_process_v1"
    assert workspace["persistence_backend"] == "loopback_127_0_0_1_8768"
    assert workspace["direct_source_retrieval_state"] is False
    assert workspace["manual_verification_states"] == [
        "plant_relay_only",
        "technician_viewed_source",
        "technician_retained_copy",
    ]
    assert "first_detected_departure" in workspace["displayed_workflow"]
    assert "missing_discriminating_context" in workspace["displayed_workflow"]
    assert "plant_reported_context_entry" in workspace["displayed_workflow"]
    assert "next_bounded_technician_check" in workspace["displayed_workflow"]
    assert "local_persistence != plant_cmms_record" in workspace["boundaries"]
    assert "local_persistence != production_service_database" in (
        workspace["boundaries"]
    )

    architecture = SPEEDWAY_WORKSPACE.read_text(encoding="utf-8")
    assert "Speedway Service Workspace" in architecture
    assert "/plant-canvas" in architecture
    assert "direct_source_retrieval" in architecture
    assert "local_persistence != plant_cmms_record" in architecture


def test_service_case_local_persistence_reality_is_bounded() -> None:
    state = load_project_state()
    persistence = state["service_case_persistence_reality"]

    assert persistence["status"] == "merged_local_runtime_capability"
    assert persistence["classification"] == "local_synthetic_development_persistence"
    assert persistence["source_baseline_main"] == CURRENT_MAIN

    service = persistence["service"]
    assert service["host"] == "127.0.0.1"
    assert service["port"] == 8768
    assert service["lan_binding"] is False
    assert service["next_same_origin_proxy"] is True

    storage = persistence["storage"]
    assert storage["format"] == "validated_json_bundle_per_service_case"
    assert storage["plaintext"] is True
    assert storage["write_strategy"] == "temporary_file_fsync_then_os_replace"
    assert storage["locking"] == "single_process_reentrant_lock"
    assert storage["multi_process_transaction_claim"] is False
    assert storage["distributed_transaction_claim"] is False

    seed = persistence["seed"]
    assert seed["path"] == "examples/speedway_service_case_workspace_seed_v1.json"
    assert seed["overwrites_existing_case"] is False
    assert seed["unresolved_context_references"] is False

    write_contract = persistence["write_contract"]
    assert write_contract["accepted_record"] == "linealert.plant-reported-context.v1"
    assert write_contract["direct_source_retrieval_state_available"] is False
    assert write_contract["identity_binding_required"] is True
    assert write_contract["reported_clock_quality_required"] is True
    assert write_contract["provenance_required"] is True

    assert "production_authentication" in persistence["not_implemented"]
    assert "encryption_at_rest" in persistence["not_implemented"]
    assert "direct_cmms_integration" in persistence["not_implemented"]
    assert "equipment_control" in persistence["not_implemented"]
    assert "local_persistence != plant_cmms_record" in persistence["boundaries"]
    assert "single_process_atomic_replace != distributed_transaction" in (
        persistence["boundaries"]
    )

    architecture = SERVICE_CASE_PERSISTENCE.read_text(encoding="utf-8")
    assert "127.0.0.1:8768" in architecture
    assert "%LOCALAPPDATA%\\LineAlert\\service-cases-v1" in architecture
    assert "plaintext local data" in architecture
    assert "local_persistence != plant_cmms_record" in architecture


def test_current_demo_boundaries_include_investigation_and_maintenance() -> None:
    state = load_project_state()
    demo = state["current_demo_reality"]
    assert "Evolving Investigation Workspace" in demo["supporting_surfaces"]
    assert demo["maintenance_lifecycle"]["synthetic_post_maintenance_target_containers"] == 10
    assert demo["trial_discipline"]["automatic_restore"] is False
    assert demo["trial_discipline"]["stack_unverified_changes"] is False
    assert "not the initial commercial LineAlert user workflow" in (
        demo["product_scope_relationship"]
    )

    investigation = demo["investigation_workspace"]
    assert investigation["state"] == (
        "merged_static_demo_pages_deployment_workflow_verified_2026_09_28"
    )
    assert "working_explanation != diagnosis" in investigation["boundaries"]
    assert "investigation_priority != causal_probability" in investigation["boundaries"]
    assert "llm_hypothesis_generation" in investigation["not_implemented"]
    assert "equipment_control" in investigation["not_implemented"]


def test_snapshot_does_not_self_reference_state_sync_as_active_work() -> None:
    state = load_project_state()
    active = state["active_work"]
    assert active["status"] == "no_active_workstream_observed_on_main_at_snapshot"
    assert active["branch"] is None
    assert active["pull_request"] is None
    assert active["objective"] is None
    assert active["permitted_paths"] == []
    assert "live_github_supersedes" in active["capability_boundary"]


def test_reasoning_node_reality_tracks_merged_bounded_substrate() -> None:
    state = load_project_state()
    reasoning = state["reasoning_node_reality"]
    assert reasoning["latest_merged_pull_request"] == 150
    assert reasoning["context_bundle"]["pull_request"] == 145
    assert reasoning["context_bundle"]["semantic_discovery_confers_authority"] is False
    assert reasoning["historian_retrieval"]["pull_request"] == 147
    assert reasoning["historian_retrieval"]["writes_or_schema_mutation"] is False

    acceptance = reasoning["live_timescale_acceptance"]
    assert acceptance["pull_request"] == 150
    assert acceptance["result"] == "passed_14_of_14"
    assert acceptance["candidate_count"] == 10
    assert acceptance["refusal_count"] == 0
    assert acceptance["truncated"] is False
    assert acceptance["current_configuration_applicability"] == "UNASSESSED"
    assert acceptance["model_invoked"] is False
    assert acceptance["authorized_action"] is False
    assert acceptance["diagnosis_established"] is False

    assert reasoning["document_retrieval"] == "not_implemented"
    assert reasoning["embeddings_or_vector_retrieval"] == "not_implemented"
    assert reasoning["local_model_integration"] == "not_implemented"
    assert reasoning["production_equipment_authority"] == "not_granted"


def test_emulated_historian_reality_is_explicit_and_non_authoritative() -> None:
    state = load_project_state()
    reality = state["emulated_historian_reality"]

    assert reality["status"] == "merged_on_main_runtime_verified"
    assert reality["classification"] == "controlled_synthetic_live_historian_emulation"
    assert reality["source_baseline_main"] == CURRENT_MAIN

    identity = reality["runtime_identity"]
    assert identity["historian_backend"] == "sqlite_emulator"
    assert identity["persistence"] == "sqlite_local_emulated"
    assert identity["source_mode"] == "controlled_synthetic_live_emulation"
    assert identity["source_classification"] == "controlled_synthetic_demo"
    assert identity["emulated"] is True

    for field in {
        "source_identity",
        "asset_identity",
        "component_identity",
        "timestamp",
        "clock_model_basis",
        "engineering_units",
        "expected_envelope",
        "configuration_version",
        "firmware_version",
        "calibration_id",
        "sampling_profile_id",
        "config_sha256",
        "scenario_phase",
        "evidence_ids",
        "reason_code",
    }:
        assert field in reality["retained_context"]

    assert "source_available=false" in reality["failure_behavior"]
    assert "emulated_history != plant_history" in reality["boundaries"]
    assert "emulated_historian != timescaledb" in reality["boundaries"]
    assert "synthetic_clock_model != verified_clock_synchronization" in (
        reality["boundaries"]
    )
    assert "simulated_departure != current_root_cause" in reality["boundaries"]

    architecture = LIVE_EMULATED_HISTORIAN.read_text(encoding="utf-8")
    assert "-UseEmulatedHistorian" in architecture
    assert "No random values are used" in architecture
    assert "127.0.0.1:8767" in architecture
    assert "sqlite_local_emulated" in architecture
    assert "emulated_history != plant_history" in architecture
    assert "emulated_historian != timescaledb" in architecture


def test_reasoning_node_tracks_current_emulated_historian_increment() -> None:
    reasoning = load_project_state()["reasoning_node_reality"]
    emulation = reasoning["historian_emulation"]

    assert emulation["status"] == "merged_on_main_runtime_verified"
    assert emulation["explicit_mode"] == "-UseEmulatedHistorian"
    assert emulation["automatic_timescale_fallback"] is False
    assert emulation["service"] == {
        "host": "127.0.0.1",
        "port": 8767,
        "lan_binding": False,
        "next_same_origin_proxy": True,
    }
    assert emulation["storage"]["backend"] == "sqlite"
    assert emulation["storage"]["wal"] is True
    assert emulation["storage"]["synchronous"] == "FULL"
    assert emulation["scenario"]["deterministic"] is True
    assert emulation["scenario"]["random_values"] is False
    assert emulation["scenario"]["scenario_length_cycles"] == 48
    assert emulation["http_external_writes"] == "refused_405"
    assert emulation["physical_state_authority"] is False
    assert emulation["production_authority"] is False
    assert emulation["timescale_replacement_claim"] is False


def test_reasoning_inputs_delivery_is_server_rendered_then_client_polled() -> None:
    state = load_project_state()
    delivery = state["reasoning_inputs_delivery_reality"]

    assert delivery["status"] == "implemented_in_current_increment"
    assert delivery["classification"] == (
        "server_rendered_initial_readiness_plus_client_polling"
    )
    assert delivery["source_baseline_main"] == CURRENT_MAIN
    assert delivery["route"] == "/reasoning"

    server = delivery["server_initial_read"]
    assert server["source"] == "loopback_127_0_0_1_8767"
    assert server["status_path"] == "/api/status"
    assert server["history_path"] == "/api/history/functional-temporal?limit=8"
    assert server["cache"] == "no-store"
    assert server["timeout_seconds"] == 1.5
    assert server["historian_write_path"] is False

    client = delivery["client_continuation"]
    assert client["same_origin"] is True
    assert client["status_path"] == "/api/historian/status"
    assert client["history_path"] == "/api/historian/functional-temporal?limit=8"
    assert client["poll_interval_seconds"] == 2.5

    acceptance = delivery["healthy_lan_initial_html_acceptance"]
    assert acceptance["http_status"] == 200
    assert "LIVE EMULATION" in acceptance["contains"]
    assert "EMULATED SOURCE LIVE" in acceptance["contains"]
    assert "Local emulated historian" in acceptance["contains"]
    assert "OFFLINE · FAIL CLOSED" in acceptance["does_not_contain"]
    assert "WAITING" in acceptance["does_not_contain"]

    assert "EVIDENCE.HISTORIAN_UNAVAILABLE" in delivery["failure_behavior"]
    assert "server_rendered_readiness != diagnosis" in delivery["boundaries"]
    assert "client_hydration_failure != historian_failure" in (
        delivery["boundaries"]
    )

    architecture = REASONING_SSR.read_text(encoding="utf-8")
    assert "dynamic server-rendered route" in architecture
    assert "EVIDENCE.HISTORIAN_UNAVAILABLE" in architecture
    assert "LIVE EMULATION" in architecture
    assert "client_hydration_failure != historian_failure" in architecture


def test_clock_integrity_reality_remains_synthetic_and_bounded() -> None:
    clock = load_project_state()["clock_integrity_reality"]
    assert clock["latest_merged_pull_request"] == 149
    assert [item["pull_request"] for item in clock["increments"]] == [
        144,
        146,
        148,
        149,
    ]
    assert clock["physical_device_clock_source"] == "not_established"
    assert clock["production_clock_synchronization_authority"] == "not_granted"
    assert clock["physical_equipment_timing_limits"] == "not_established"


def test_current_equipment_reality_does_not_claim_commissioning() -> None:
    state = load_project_state()
    labeler = state["equipment_and_source_reality"]["labeler_2"]
    assert labeler["physical_asset_connected"] is False
    assert labeler["oem_manual_observed_in_repository"] is False
    assert labeler["commissioned_machine_profile_observed"] is False
    assert labeler["runtime_control_path_observed"] is False

    material = state["equipment_and_source_reality"][
        "available_repository_material"
    ]
    assert material["speedway_route_scope"] == "synthetic_demo"
    assert material["physics_roll_profile"] == "illustrative_non_oem"
    assert material["reasoning_context_bundle"] == (
        "controlled_synthetic_software_contract"
    )
    assert material["reasoning_historian_retrieval"] == (
        "controlled_read_only_local_historian_contract"
    )
    assert material["reasoning_live_timescale_acceptance"] == (
        "controlled_synthetic_local_acceptance"
    )


def test_net_zero_sync_probe_history_is_preserved_transparently() -> None:
    provenance = load_project_state()["governance_and_provenance"]
    housekeeping = provenance["net_zero_main_housekeeping"]
    assert [item["commit"] for item in housekeeping] == [
        "ccc3b49fd4f1db48f89ce7b0b1dd265b8278bb1f",
        "acfd9791fa4eef624098cf69805893389afd7ef2",
    ]
    assert "No residual repository content" in (
        provenance["net_zero_housekeeping_boundary"]
    )


def test_ci_workflow_verifies_literal_event_sha() -> None:
    state = load_project_state()
    policy = state["ci_policy"]
    assert policy["required_checkout"] == "literal_event_sha"
    assert policy["pull_request_sha"] == (
        "github.event.pull_request.head.sha"
    )
    assert policy["push_sha"] == "github.sha"
    assert policy["verification"] == (
        "git_rev_parse_HEAD_must_equal_expected_sha"
    )

    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    assert "name: Checkout pull-request head" in workflow
    assert "ref: ${{ github.event.pull_request.head.sha }}" in workflow
    assert "name: Checkout pushed commit" in workflow
    assert "ref: ${{ github.sha }}" in workflow
    assert "name: Verify exact checkout provenance" in workflow
    assert 'actual_sha="$(git rev-parse HEAD)"' in workflow
    assert 'test "$actual_sha" = "$EXPECTED_SHA"' in workflow


def test_transaction_inventory_matches_pr38_boundary() -> None:
    inventory = TRANSACTION_INVENTORY.read_text(encoding="utf-8")
    assert PR38_MERGE in inventory
    assert "PR #38" in inventory
    assert "`MosaicTransaction`" in inventory
    assert "FW-01" in inventory
    assert "FW-04" in inventory
    assert "resolved" in inventory
    assert "arbitrary external side effects" in inventory
    assert "software atomicity != equipment safety" in inventory


def test_publication_and_readme_guidance_remain_current() -> None:
    project_guidance = PROJECT_GUIDANCE.read_text(encoding="utf-8")
    assert "## Publication rule" in project_guidance
    assert "does not require another pull request merely to record its own merge" in (
        project_guidance
    )
    assert "live_scope_changed_before_merge = corrective_sync_required" in (
        project_guidance
    )

    readme = " ".join(ROOT_README.read_text(encoding="utf-8").split())
    assert "Issue #27 defines the risk-tiered workflow" in readme
    assert "Issue #15 acceptance evidence exists" not in readme
    assert "disposable Stage 1 simulator exception" in readme
    assert "LineAlert v1 is centered on Speedway service / maintenance technicians" in readme
    assert "Direct client CMMS integration is not required for v1" in readme
    assert "First detected departure is not root-cause proof" in readme
    assert "service-case and plant-reported-context contracts" in readme
    assert "examples/speedway_service_case_v1.json" in readme
    assert "synthetic Speedway Service Workspace" in readme
    assert "/plant-canvas" in readme
    assert "loopback-only local persistence service on port 8768" in readme
    assert "plaintext atomic JSON" in readme
    assert "service-case-local-persistence-v1.md" in readme
    assert "-UseEmulatedHistorian" in readme
    assert "live-emulated-historian-v1.md" in readme
    assert "does not represent physical plant history" in readme

    lineage = LINEAGE_GUIDANCE.read_text(encoding="utf-8")
    assert "green_ci != authorized_merge" in lineage
    assert "historical_pattern != current_root_cause" in lineage
    assert "successful_test != safe_production_change" in lineage


def test_production_deployment_and_equipment_reality_remain_bounded() -> None:
    state = load_project_state()
    assert state["deployment_state"] == {
        "status": "not_deployed",
        "azure_lab_resources": "not_observed",
        "physical_equipment_connection": "not_observed",
        "network_listener": "not_observed",
        "equipment_control_path": "not_observed",
    }
    scope = state["deployment_state_scope"]
    assert "static GitHub Pages deployment" in scope
    assert "reverified successfully on 2026-09-28" in scope
    assert "distinct from production runtime" in scope
