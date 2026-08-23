"""Deterministic semantic admission for live observation snapshots."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def load_semantic_binding_profile(path: Path) -> dict[str, Any]:
    profile = json.loads(path.read_text(encoding="utf-8"))
    if profile.get("schema_version") != "linealert.semantic-binding-profile.v1":
        raise ValueError("unsupported semantic binding profile")
    return profile


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def evaluate_semantic_admission(
    snapshot: dict[str, Any],
    profile: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Admit only signals whose declared evidence contract matches exactly."""

    evaluated_at = now or datetime.now(UTC)
    snapshot_matches = (
        snapshot.get("profile") == profile.get("source_profile")
        and snapshot.get("source_id") == profile.get("source_id")
        and snapshot.get("asset_id") == profile.get("asset_id")
        and snapshot.get("read_only") is True
        and snapshot.get("connected") is True
    )
    decisions: dict[str, Any] = {}
    for name, binding in profile.get("bindings", {}).items():
        signal = snapshot.get("signals", {}).get(name)
        reason = "EVIDENCE.SEMANTIC_BINDING_DECLARED_INADMISSIBLE"
        admitted = False
        if binding.get("admitted") is True:
            if not snapshot_matches:
                reason = "EVIDENCE.SEMANTIC_SNAPSHOT_SCOPE_MISMATCH"
            elif not isinstance(signal, dict):
                reason = "EVIDENCE.SEMANTIC_SIGNAL_MISSING"
            elif signal.get("node_id") != binding.get("node_id"):
                reason = "EVIDENCE.SEMANTIC_NODE_ID_MISMATCH"
            elif signal.get("unit") != binding.get("unit"):
                reason = "EVIDENCE.SEMANTIC_UNIT_MISMATCH"
            elif signal.get("quality") != "good":
                reason = "EVIDENCE.SEMANTIC_QUALITY_REFUSED"
            else:
                observed = _parse_timestamp(signal.get("source_timestamp"))
                age_ms = (
                    (evaluated_at - observed).total_seconds() * 1000
                    if observed is not None
                    else None
                )
                if age_ms is None or age_ms < 0 or age_ms > binding.get("max_age_ms", 0):
                    reason = "EVIDENCE.SEMANTIC_FRESHNESS_REFUSED"
                else:
                    admitted = True
                    reason = "EVIDENCE.SEMANTIC_BINDING_ADMITTED"
        decisions[name] = {
            "admitted": admitted,
            "reason_code": reason,
            "semantic": binding.get("semantic"),
            "scope": binding.get("scope"),
        }

    admitted_count = sum(1 for decision in decisions.values() if decision["admitted"])
    return {
        "schema_version": "linealert.semantic-admission-result.v1",
        "profile_id": profile.get("profile_id"),
        "profile_version": profile.get("profile_version"),
        "scope": profile.get("scope"),
        "admitted_count": admitted_count,
        "total_count": len(decisions),
        "reason_code": (
            "EVIDENCE.SEMANTIC_ADMISSION_COMPLETE"
            if admitted_count == len(decisions)
            else "EVIDENCE.SEMANTIC_ADMISSION_PARTIAL"
            if admitted_count
            else "EVIDENCE.SEMANTIC_BINDING_REQUIRED"
        ),
        "signals": decisions,
    }
