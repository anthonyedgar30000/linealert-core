from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_operating_mode_profile(path: Path) -> dict[str, Any]:
    profile = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "profile_id",
        "profile_version",
        "default_mode",
        "modes",
    }
    if not required.issubset(profile):
        raise ValueError("operating mode profile is incomplete")
    if profile["default_mode"] not in profile["modes"]:
        raise ValueError("default operating mode is not declared")
    return profile


def evaluate_operating_mode(
    *,
    configured_mode: str,
    source_kinds: list[str],
    profile: dict[str, Any],
) -> dict[str, Any]:
    unique_sources = sorted(set(source_kinds))
    result = {
        "schema_version": "linealert.operating-mode-assessment.v1",
        "profile_id": profile["profile_id"],
        "profile_version": profile["profile_version"],
        "configured_mode": configured_mode,
        "source_kinds": unique_sources,
        "scope": "none",
        "source_admitted": False,
        "reason_code": "EVIDENCE.OPERATING_MODE_UNKNOWN",
        "authorized_action": False,
    }

    mode = profile["modes"].get(configured_mode)
    if mode is None:
        return result

    result["scope"] = mode["scope"]
    if len(unique_sources) != 1:
        result["reason_code"] = (
            "EVIDENCE.OPERATING_MODE_MIXED_SOURCES_REFUSED"
            if len(unique_sources) > 1
            else "EVIDENCE.OPERATING_MODE_SOURCE_MISSING"
        )
        return result

    source_kind = unique_sources[0]
    if source_kind not in mode["allowed_source_kinds"]:
        result["reason_code"] = "EVIDENCE.OPERATING_MODE_SOURCE_REFUSED"
        return result

    result["source_admitted"] = True
    result["reason_code"] = "EVIDENCE.OPERATING_MODE_SOURCE_ADMITTED"
    return result


def enforce_operating_mode(
    payload: dict[str, Any],
    assessment: dict[str, Any],
) -> dict[str, Any]:
    payload["operating_mode"] = assessment
    if assessment["source_admitted"]:
        return payload

    admission = payload.get("semantic_admission")
    if admission:
        admission["admitted_count"] = 0
        admission["scope"] = "disabled"
        admission["reason_code"] = "EVIDENCE.OPERATING_MODE_SOURCE_REFUSED"
        for decision in admission.get("signals", {}).values():
            decision["admitted"] = False
            decision["scope"] = "disabled"
            decision["reason_code"] = "EVIDENCE.OPERATING_MODE_SOURCE_REFUSED"
    payload["reason_code"] = "EVIDENCE.OPERATING_MODE_SOURCE_REFUSED"
    return payload
