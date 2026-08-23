import json
from pathlib import Path

import pytest

from linealert_core.troubleshooting_routing import evaluate_troubleshooting_route

PROFILE = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "profiles"
        / "speedway-labeler-troubleshooting-v1.routes.json"
    ).read_text(encoding="utf-8")
)

CASES = [
    (
        "LINEALERT.DEMO.LABEL_ALIGNMENT_OFF",
        ["arrival_phase", "merge_spacing"],
        "LABEL_ALIGNMENT_OFF",
    ),
    (
        "LINEALERT.DEMO.LABEL_FOLDS",
        ["surface_slip", "contact_state"],
        "LABEL_FOLDS",
    ),
    (
        "LINEALERT.DEMO.LABEL_STRETCH_LINES",
        ["web_tension"],
        "LABEL_STRETCH_LINES",
    ),
    (
        "LINEALERT.DEMO.LABEL_BUBBLES",
        ["application_pressure", "contact_time"],
        "LABEL_BUBBLES",
    ),
    (
        "LINEALERT.DEMO.MULTIPLE_LABELS",
        ["gap_detection", "label_spacing"],
        "MULTIPLE_LABELS",
    ),
]


def finding(
    finding_id: str,
    semantics: list[str],
    *,
    scope: str = "synthetic_demo",
    status: str = "admitted",
    contradictions: list[str] | None = None,
) -> dict[str, object]:
    return {
        "finding_id": finding_id,
        "evidence_scope": scope,
        "evidence_status": status,
        "observed_semantics": semantics,
        "contradictions": contradictions or [],
    }


@pytest.mark.parametrize(("finding_id", "semantics", "procedure_id"), CASES)
def test_routes_declared_synthetic_findings(
    finding_id: str, semantics: list[str], procedure_id: str
) -> None:
    result = evaluate_troubleshooting_route(
        finding(finding_id, semantics),
        PROFILE,
        role="operator",
    )

    assert result["decision"] == "ROUTE"
    assert result["procedure_id"] == procedure_id
    assert result["authorized_action"] is False
    assert result["guide_path"] == "/troubleshooting-guide.html"


def test_refuses_simulator_only_live_evidence() -> None:
    result = evaluate_troubleshooting_route(
        finding(
            "LINEALERT.DEMO.LABEL_ALIGNMENT_OFF",
            ["arrival_phase", "merge_spacing"],
            scope="simulator_only",
        ),
        PROFILE,
        role="operator",
    )

    assert result["decision"] == "REFUSE"
    assert result["reason_code"] == "EVIDENCE.TROUBLESHOOTING_SCOPE_INADMISSIBLE"
    assert result["procedure_id"] is None


def test_refuses_inadmissible_finding() -> None:
    result = evaluate_troubleshooting_route(
        finding(
            "LINEALERT.DEMO.LABEL_FOLDS",
            ["surface_slip", "contact_state"],
            status="refused",
        ),
        PROFILE,
        role="maintenance",
    )

    assert result["decision"] == "REFUSE"
    assert result["reason_code"] == "EVIDENCE.TROUBLESHOOTING_FINDING_INADMISSIBLE"


def test_escalates_contradictory_evidence() -> None:
    result = evaluate_troubleshooting_route(
        finding(
            "LINEALERT.DEMO.LABEL_BUBBLES",
            ["application_pressure", "contact_time"],
            contradictions=["pressure_normal"],
        ),
        PROFILE,
        role="maintenance",
    )

    assert result["decision"] == "ESCALATE"
    assert result["reason_code"] == "EVIDENCE.TROUBLESHOOTING_CONTRADICTION"


def test_escalates_unknown_finding() -> None:
    result = evaluate_troubleshooting_route(
        finding("LINEALERT.DEMO.UNKNOWN", ["unknown"]),
        PROFILE,
        role="engineering",
    )

    assert result["decision"] == "ESCALATE"
    assert result["reason_code"] == "LINEALERT.TROUBLESHOOTING_ROUTE_UNKNOWN"


def test_escalates_incomplete_semantics() -> None:
    result = evaluate_troubleshooting_route(
        finding("LINEALERT.DEMO.MULTIPLE_LABELS", ["gap_detection"]),
        PROFILE,
        role="technician",
    )

    assert result["decision"] == "ESCALATE"
    assert result["reason_code"] == "EVIDENCE.TROUBLESHOOTING_SEMANTICS_INCOMPLETE"


def test_refuses_unsupported_role() -> None:
    result = evaluate_troubleshooting_route(
        finding(
            "LINEALERT.DEMO.LABEL_STRETCH_LINES",
            ["web_tension"],
        ),
        PROFILE,
        role="administrator",
    )

    assert result["decision"] == "REFUSE"
    assert result["reason_code"] == "AUTHORITY.TROUBLESHOOTING_ROLE_UNSUPPORTED"
