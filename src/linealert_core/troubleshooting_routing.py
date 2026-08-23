from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_ROUTE = "ROUTE"
_REFUSE = "REFUSE"
_ESCALATE = "ESCALATE"


def load_troubleshooting_route_profile(path: Path) -> dict[str, Any]:
    profile = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "profile_id",
        "profile_version",
        "guide_path",
        "allowed_finding_scope",
        "procedures",
        "role_checks",
    }
    if not required.issubset(profile):
        raise ValueError("troubleshooting route profile is incomplete")
    return profile


def _decision(
    profile: dict[str, Any],
    *,
    decision: str,
    reason_code: str,
    procedure_id: str | None = None,
    first_check: str | None = None,
    role_instruction: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "linealert.troubleshooting-route-result.v1",
        "profile_id": profile["profile_id"],
        "profile_version": profile["profile_version"],
        "decision": decision,
        "reason_code": reason_code,
        "procedure_id": procedure_id,
        "first_check": first_check,
        "role_instruction": role_instruction,
        "guide_path": profile["guide_path"] if procedure_id else None,
        "authorized_action": False,
    }


def evaluate_troubleshooting_route(
    finding: dict[str, Any],
    profile: dict[str, Any],
    *,
    role: str,
) -> dict[str, Any]:
    """Route an admitted bounded finding without authorizing equipment action."""

    role_instruction = profile["role_checks"].get(role)
    if role_instruction is None:
        return _decision(
            profile,
            decision=_REFUSE,
            reason_code="AUTHORITY.TROUBLESHOOTING_ROLE_UNSUPPORTED",
        )

    if finding.get("evidence_scope") != profile["allowed_finding_scope"]:
        return _decision(
            profile,
            decision=_REFUSE,
            reason_code="EVIDENCE.TROUBLESHOOTING_SCOPE_INADMISSIBLE",
            role_instruction=role_instruction,
        )

    if finding.get("evidence_status") != "admitted":
        return _decision(
            profile,
            decision=_REFUSE,
            reason_code="EVIDENCE.TROUBLESHOOTING_FINDING_INADMISSIBLE",
            role_instruction=role_instruction,
        )

    if finding.get("contradictions"):
        return _decision(
            profile,
            decision=_ESCALATE,
            reason_code="EVIDENCE.TROUBLESHOOTING_CONTRADICTION",
            role_instruction=role_instruction,
        )

    procedure = profile["procedures"].get(finding.get("finding_id"))
    if procedure is None:
        return _decision(
            profile,
            decision=_ESCALATE,
            reason_code="LINEALERT.TROUBLESHOOTING_ROUTE_UNKNOWN",
            role_instruction=role_instruction,
        )

    observed_semantics = set(finding.get("observed_semantics", []))
    required_semantics = set(procedure["required_semantics"])
    if not required_semantics.issubset(observed_semantics):
        return _decision(
            profile,
            decision=_ESCALATE,
            reason_code="EVIDENCE.TROUBLESHOOTING_SEMANTICS_INCOMPLETE",
            role_instruction=role_instruction,
        )

    return _decision(
        profile,
        decision=_ROUTE,
        reason_code="LINEALERT.TROUBLESHOOTING_ROUTE_SELECTED",
        procedure_id=procedure["procedure_id"],
        first_check=procedure["default_check"],
        role_instruction=role_instruction,
    )
