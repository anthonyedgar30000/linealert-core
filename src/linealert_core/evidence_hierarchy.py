from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_evidence_hierarchy_profile(path: Path) -> dict[str, Any]:
    profile = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "profile_id",
        "profile_version",
        "levels",
        "physical_claim_prefixes",
        "corroboration",
    }
    if not required.issubset(profile):
        raise ValueError("evidence hierarchy profile is incomplete")
    return profile


def _is_physical_claim(claim_id: str, profile: dict[str, Any]) -> bool:
    return any(claim_id.startswith(prefix) for prefix in profile["physical_claim_prefixes"])


def classify_observation(
    observation: dict[str, Any],
    *,
    claim_id: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    category = observation.get("category", "unknown")
    base_level = profile["levels"].get(category, 0)
    result = {
        "observation_id": observation.get("observation_id"),
        "category": category,
        "claim_id": claim_id,
        "base_level": base_level,
        "admissible": False,
        "supports": observation.get("supports"),
        "failure_domain": observation.get("failure_domain"),
        "reason_code": "EVIDENCE.HIERARCHY_UNKNOWN",
    }

    if base_level == 0:
        return result

    if not observation.get("semantic_admitted", False):
        result["reason_code"] = "EVIDENCE.HIERARCHY_SEMANTICALLY_INADMISSIBLE"
        return result

    supported_claims = observation.get("supported_claims", [])
    if claim_id not in supported_claims:
        result["reason_code"] = "EVIDENCE.HIERARCHY_CLAIM_IRRELEVANT"
        return result

    if observation.get("scope") == "simulator_only" and _is_physical_claim(claim_id, profile):
        result["reason_code"] = "EVIDENCE.HIERARCHY_SIMULATOR_PHYSICAL_CLAIM_REFUSED"
        return result

    if observation.get("quality") != profile["required_quality"]:
        result["reason_code"] = "EVIDENCE.HIERARCHY_QUALITY_UNACCEPTABLE"
        return result

    if not observation.get("fresh", False):
        result["reason_code"] = "EVIDENCE.HIERARCHY_STALE"
        return result

    if base_level >= 2:
        if not observation.get("binding_verified", False):
            result["reason_code"] = "EVIDENCE.HIERARCHY_BINDING_UNVERIFIED"
            return result
        if observation.get("calibration_state") != profile["required_calibration_state"]:
            result["reason_code"] = "EVIDENCE.HIERARCHY_CALIBRATION_UNACCEPTABLE"
            return result

    if base_level == 5:
        if not observation.get("acceptance_plan_id"):
            result["reason_code"] = "EVIDENCE.HIERARCHY_ACCEPTANCE_PLAN_MISSING"
            return result
        if observation.get("outcome_result") not in profile["verified_outcome_results"]:
            result["reason_code"] = "EVIDENCE.HIERARCHY_OUTCOME_UNVERIFIED"
            return result

    result["admissible"] = True
    result["reason_code"] = f"EVIDENCE.HIERARCHY_LEVEL_{base_level}_ADMITTED"
    return result


def evaluate_claim_evidence(
    *,
    claim_id: str,
    observations: list[dict[str, Any]],
    profile: dict[str, Any],
) -> dict[str, Any]:
    classified = [
        classify_observation(item, claim_id=claim_id, profile=profile)
        for item in observations
    ]
    admitted = [item for item in classified if item["admissible"]]
    supporting = [item for item in admitted if item["supports"] is True]
    opposing = [item for item in admitted if item["supports"] is False]

    status = "INSUFFICIENT"
    level = max((item["base_level"] for item in admitted), default=0)
    reason_code = "EVIDENCE.HIERARCHY_INSUFFICIENT"

    if supporting and opposing:
        status = "CONTRADICTED"
        reason_code = "EVIDENCE.HIERARCHY_CONTRADICTION_PRESERVED"
    elif supporting:
        status = "SUPPORTED"
        reason_code = "EVIDENCE.HIERARCHY_CLAIM_SUPPORTED"
        corroboration = profile["corroboration"]
        eligible = [
            item
            for item in supporting
            if item["base_level"] >= corroboration["minimum_source_level"]
        ]
        failure_domains = {
            item["failure_domain"] for item in eligible if item["failure_domain"]
        }
        if (
            len(eligible) >= corroboration["minimum_sources"]
            and len(failure_domains) >= corroboration["minimum_failure_domains"]
            and level < 5
        ):
            level = corroboration["derived_level"]
            reason_code = "EVIDENCE.HIERARCHY_INDEPENDENTLY_CORROBORATED"
    elif opposing:
        status = "REFUTED"
        reason_code = "EVIDENCE.HIERARCHY_CLAIM_REFUTED"

    return {
        "schema_version": "linealert.claim-evidence-assessment.v1",
        "profile_id": profile["profile_id"],
        "profile_version": profile["profile_version"],
        "claim_id": claim_id,
        "status": status,
        "evidence_level": level,
        "reason_code": reason_code,
        "observations": classified,
        "supporting_observation_ids": [
            item["observation_id"] for item in supporting
        ],
        "opposing_observation_ids": [
            item["observation_id"] for item in opposing
        ],
        "authorized_action": False,
    }
