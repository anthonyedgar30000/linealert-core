from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode

import pytest

from linealert_core.historian import ConditionHistoryRecord
from linealert_core.historian_service import (
    HistorianServiceStatus,
    condition_localization_request_from_query,
    functional_temporal_selection_spec_from_query,
    handler_for,
    historian_condition_localization_from_query,
    history_time_from_query,
    load_localization_topology_authority,
    measurement_from_payload,
)


def _condition_payload() -> dict[str, object]:
    return {
        "signal": "label_presentation_delay_ms",
        "value": 550.0,
        "unit": "ms",
        "min_value": 50.0,
        "max_value": 350.0,
        "asset_id": "LABELER-DEMO-01",
        "rule_id": "label-presentation-delay",
        "correlation_id": "drift-cycle-2010",
        "source_timestamp": "2026-08-24T12:00:00+00:00",
        "start_timestamp": "2026-08-24T11:59:59.450000+00:00",
        "end_timestamp": "2026-08-24T12:00:00+00:00",
        "start_event_id": "command-2010",
        "end_event_id": "peel-2010",
        "start_source_id": "plc-labeler-demo",
        "end_source_id": "plc-labeler-demo",
        "topology_from": "LabelFeedCommand",
        "topology_to": "LabelAtPeelPoint",
        "temporal_rule_status": "late",
        "semantic": "label presentation delay",
        "scope": "label-application-station",
        "relationship_id": "relationship:label-presentation-delay",
        "observation_id": "LABELER-DEMO-01:drift-cycle-2010:label_presentation_delay_ms:2026",
        "quality": "good",
        "reason_code": "EVIDENCE.RELATIONSHIP_DELAY_MEASURED",
        "clock_evidence": {
            "start_clock_quality": "synchronized",
            "end_clock_quality": "synchronized",
            "basis": "same_source_relative_interval",
            "retained_uncertainty": "same source clock",
        },
    }


def test_measurement_from_payload_preserves_admitted_relationship_evidence() -> None:
    measurement = measurement_from_payload(_condition_payload())

    assert measurement.observation.value == 550.0
    assert measurement.observation.min_value == 50.0
    assert measurement.observation.max_value == 350.0
    assert measurement.observation.relationship_id == "relationship:label-presentation-delay"
    assert measurement.observation.temporal_rule_status == "late"
    assert measurement.clock_evidence.basis == "same_source_relative_interval"


def test_measurement_from_payload_rejects_incomplete_condition() -> None:
    payload = _condition_payload()
    del payload["relationship_id"]

    with pytest.raises(ValueError, match="relationship_id"):
        measurement_from_payload(payload)


def test_historian_service_status_returns_detached_payload() -> None:
    status = HistorianServiceStatus()
    status.update(connected=True, source_available=True, latest_condition_count=10)

    first = status.get()
    first["connected"] = False

    assert status.get()["connected"] is True
    assert status.get()["latest_condition_count"] == 10


def test_history_time_from_query_requires_timezone_aware_iso8601() -> None:
    parsed = history_time_from_query("2026-09-14T15:42:00Z", "from_time")

    assert parsed is not None
    assert parsed.isoformat() == "2026-09-14T15:42:00+00:00"
    assert history_time_from_query(None, "to_time") is None

    with pytest.raises(ValueError, match="timezone-aware"):
        history_time_from_query("2026-09-14T15:42:00", "from_time")
    with pytest.raises(ValueError, match="ISO 8601"):
        history_time_from_query("not-a-time", "from_time")


def test_functional_temporal_selection_spec_from_query_preserves_explicit_scope() -> None:
    query = {
        "reference_label": ["Approved reference cycle"],
        "reference_cycle_id": ["commissioned-cycle-42"],
        "reference_phase_id": ["LABEL_PRESENTED"],
        "reference_record_kind": ["GUARD"],
        "reference_from_time": ["2026-03-12T14:29:00Z"],
        "reference_to_time": ["2026-03-12T14:31:00Z"],
        "reference_limit": ["250"],
    }

    spec = functional_temporal_selection_spec_from_query(
        query,
        prefix="reference",
        asset_id="LABELER-DEMO-01",
        default_limit=1000,
    )

    assert spec.label == "Approved reference cycle"
    assert spec.asset_id == "LABELER-DEMO-01"
    assert spec.cycle_id == "commissioned-cycle-42"
    assert spec.phase_id == "LABEL_PRESENTED"
    assert spec.record_kind is not None
    assert spec.record_kind.value == "GUARD"
    assert spec.limit == 250
    assert spec.from_time is not None
    assert spec.from_time.isoformat() == "2026-03-12T14:29:00+00:00"
    assert spec.to_time is not None
    assert spec.to_time.isoformat() == "2026-03-12T14:31:00+00:00"


def test_functional_temporal_selection_spec_from_query_rejects_missing_label() -> None:
    with pytest.raises(ValueError, match="reference_label is required"):
        functional_temporal_selection_spec_from_query(
            {"reference_cycle_id": ["cycle-42"]},
            prefix="reference",
            asset_id="LABELER-DEMO-01",
            default_limit=1000,
        )


def test_functional_temporal_selection_spec_from_query_rejects_invalid_kind_and_limit() -> None:
    with pytest.raises(ValueError, match="reference_record_kind is invalid"):
        functional_temporal_selection_spec_from_query(
            {
                "reference_label": ["Reference"],
                "reference_cycle_id": ["cycle-42"],
                "reference_record_kind": ["UNKNOWN_KIND"],
            },
            prefix="reference",
            asset_id="LABELER-DEMO-01",
            default_limit=1000,
        )

    with pytest.raises(ValueError, match="reference_limit must be an integer"):
        functional_temporal_selection_spec_from_query(
            {
                "reference_label": ["Reference"],
                "reference_cycle_id": ["cycle-42"],
                "reference_limit": ["many"],
            },
            prefix="reference",
            asset_id="LABELER-DEMO-01",
            default_limit=1000,
        )


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _LocalizationHistorian:
    def __init__(
        self,
        records: tuple[ConditionHistoryRecord, ...],
        *,
        truncated: bool = False,
    ) -> None:
        self.records = records
        self.truncated = truncated
        self.calls: list[dict[str, object]] = []

    def select_condition_history_records(
        self,
        *,
        limit: int = 240,
        asset_id: str | None = None,
        relationship_id: str | None = None,
        episode_id: str | None = None,
        cycle_id: str | None = None,
        phase_id: str | None = None,
        from_time: datetime | None = None,
        to_time: datetime | None = None,
    ) -> tuple[tuple[ConditionHistoryRecord, ...], bool]:
        self.calls.append(
            {
                "limit": limit,
                "asset_id": asset_id,
                "relationship_id": relationship_id,
                "episode_id": episode_id,
                "cycle_id": cycle_id,
                "phase_id": phase_id,
                "from_time": from_time,
                "to_time": to_time,
            }
        )
        return self.records, self.truncated


def _localization_record(
    *,
    offset_seconds: int,
    value: float,
) -> ConditionHistoryRecord:
    observed_at = datetime(2026, 9, 14, 11, 37, tzinfo=UTC) + timedelta(seconds=offset_seconds)
    outside = value > 350.0
    return ConditionHistoryRecord(
        observed_at=observed_at,
        observation_id=f"obs-{offset_seconds}",
        episode_id="incident-42",
        asset_id="LABELER-DEMO-01",
        relationship_id="relationship:label-presentation-delay",
        signal="label_presentation_delay_ms",
        value=value,
        unit="ms",
        min_value=50.0,
        max_value=350.0,
        temporal_rule_status="late" if outside else "within",
        quality="good",
        reason_code="EVIDENCE.RELATIONSHIP_DELAY_MEASURED",
        correlation_id=f"cycle-{offset_seconds}",
        topology_from="LabelFeedCommand",
        topology_to="LabelAtPeelPoint",
        source_mode="replay",
        cycle_id=f"cycle-{offset_seconds}",
        operating_context={
            "configuration_version": "demo-config-v1",
            "firmware_version": "demo-fw-v1",
            "recipe_id": "500ml-round",
        },
        clock_evidence={"basis": "same_source_relative_interval"},
    )


def _localization_records() -> tuple[ConditionHistoryRecord, ...]:
    return tuple(
        _localization_record(offset_seconds=index * 60, value=value)
        for index, value in enumerate([200.0, 500.0, 510.0, 520.0])
    )


def _localization_query() -> dict[str, list[str]]:
    return {
        "asset_id": ["LABELER-DEMO-01"],
        "selection_label": ["Incident persistence window"],
        "episode_id": ["incident-42"],
        "target_relationship_id": ["relationship:label-presentation-delay"],
        "limit": ["250"],
    }


def test_localization_topology_authority_binds_demo_asset_profile_and_hash() -> None:
    authority = load_localization_topology_authority(
        PROJECT_ROOT / "examples" / "labeler_demo_config.json"
    )

    assert authority.asset_id == "LABELER-DEMO-01"
    assert authority.profile_id == "generic-pressure-sensitive-labeler-demo-v1"
    assert authority.source_name == "labeler_demo_config.json"
    assert len(authority.source_sha256) == 64
    assert authority.topology.has_edge("LabelFeedCommand", "LabelAtPeelPoint")
    policy = authority.persistence_policies.require("relationship:label-presentation-delay")
    assert policy.policy_id == "label-presentation-persistence-v1"
    assert policy.policy_revision == "1"
    assert policy.required_outside == 3
    assert policy.window_size == 4


def test_condition_localization_request_parser_preserves_scope_without_rule_override() -> None:
    query = _localization_query()
    query["from_time"] = ["2026-09-14T11:37:00Z"]
    query["to_time"] = ["2026-09-14T11:40:00Z"]

    selection, target = condition_localization_request_from_query(
        query,
        default_limit=240,
    )

    assert selection.label == "Incident persistence window"
    assert selection.asset_id == "LABELER-DEMO-01"
    assert selection.episode_id == "incident-42"
    assert selection.limit == 250
    assert selection.from_time is not None
    assert selection.from_time.isoformat() == "2026-09-14T11:37:00+00:00"
    assert selection.to_time is not None
    assert selection.to_time.isoformat() == "2026-09-14T11:40:00+00:00"
    assert target == "relationship:label-presentation-delay"


def test_condition_localization_request_parser_rejects_hidden_dependency_filter() -> None:
    query = _localization_query()
    query["relationship_id"] = ["relationship:label-presentation-delay"]

    with pytest.raises(ValueError, match="dependency evidence must remain visible"):
        condition_localization_request_from_query(query, default_limit=240)


def test_condition_localization_request_parser_rejects_caller_rule_override() -> None:
    query = _localization_query()
    query["required_outside"] = ["1"]
    query["window_size"] = ["1"]

    with pytest.raises(ValueError, match="resolved from machine configuration"):
        condition_localization_request_from_query(query, default_limit=240)


def test_historian_condition_localization_returns_bounded_result_and_topology_provenance() -> None:
    historian = _LocalizationHistorian(_localization_records())
    authority = load_localization_topology_authority(
        PROJECT_ROOT / "examples" / "labeler_demo_config.json"
    )

    payload = historian_condition_localization_from_query(
        historian,  # type: ignore[arg-type]
        _localization_query(),
        authority,
    )

    assert payload["schema_version"] == "linealert.configured-condition-localization.v1"
    assert payload["disposition"] == "READY"
    localization = payload["localization"]
    assert isinstance(localization, dict)
    assert localization["disposition"] == "PERSISTENCE_ESTABLISHED"
    onset = localization["onset"]
    assert isinstance(onset, dict)
    assert onset["outside_count"] == 3
    assert onset["window_count"] == 4
    policy = payload["persistence_policy"]
    assert isinstance(policy, dict)
    policy_payload = policy["policy"]
    assert isinstance(policy_payload, dict)
    assert policy_payload["policy_id"] == "label-presentation-persistence-v1"
    assert policy_payload["policy_revision"] == "1"
    assert policy_payload["required_outside"] == 3
    assert policy_payload["window_size"] == 4
    policy_application = payload["policy_application"]
    assert isinstance(policy_application, dict)
    assert policy_application["mode"] == "CURRENT_CONFIG_APPLIED_TO_SELECTED_HISTORY"
    assert policy_application["historical_policy_equivalence"] == "UNVERIFIED"
    topology_authority = payload["topology_authority"]
    assert isinstance(topology_authority, dict)
    assert topology_authority["asset_id"] == "LABELER-DEMO-01"
    assert topology_authority["profile_id"] == ("generic-pressure-sensitive-labeler-demo-v1")
    assert topology_authority["source_name"] == "labeler_demo_config.json"
    assert len(topology_authority["source_sha256"]) == 64
    assert historian.calls[0]["relationship_id"] is None


def test_historian_condition_localization_rejects_asset_topology_mismatch() -> None:
    historian = _LocalizationHistorian(_localization_records())
    authority = load_localization_topology_authority(
        PROJECT_ROOT / "examples" / "labeler_demo_config.json"
    )
    query = _localization_query()
    query["asset_id"] = ["OTHER-ASSET"]

    with pytest.raises(ValueError, match="does not match"):
        historian_condition_localization_from_query(
            historian,  # type: ignore[arg-type]
            query,
            authority,
        )


def _request_localization_endpoint(
    historian: _LocalizationHistorian,
    *,
    with_authority: bool,
) -> tuple[int, dict[str, object]]:
    status = HistorianServiceStatus()
    authority = (
        load_localization_topology_authority(PROJECT_ROOT / "examples" / "labeler_demo_config.json")
        if with_authority
        else None
    )
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        handler_for(
            historian,  # type: ignore[arg-type]
            status,
            localization_authority=authority,
        ),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        flat_query = {key: values[0] for key, values in _localization_query().items()}
        connection.request(
            "GET",
            "/api/history/conditions/localize?" + urlencode(flat_query),
        )
        response = connection.getresponse()
        body = json.loads(response.read().decode("utf-8"))
        return response.status, body
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_localization_endpoint_executes_selector_and_localizer() -> None:
    status_code, payload = _request_localization_endpoint(
        _LocalizationHistorian(_localization_records()),
        with_authority=True,
    )

    assert status_code == 200
    assert payload["schema_version"] == "linealert.configured-condition-localization.v1"
    assert payload["disposition"] == "READY"
    policy = payload["persistence_policy"]
    assert isinstance(policy, dict)
    policy_payload = policy["policy"]
    assert isinstance(policy_payload, dict)
    assert policy_payload["policy_id"] == "label-presentation-persistence-v1"
    assert "required_outside" not in _localization_query()
    assert "window_size" not in _localization_query()
    localization = payload["localization"]
    assert isinstance(localization, dict)
    assert localization["disposition"] == "PERSISTENCE_ESTABLISHED"


def test_localization_endpoint_refuses_when_topology_authority_is_unconfigured() -> None:
    status_code, payload = _request_localization_endpoint(
        _LocalizationHistorian(_localization_records()),
        with_authority=False,
    )

    assert status_code == 503
    assert payload["disposition"] == "UNAVAILABLE"
    assert payload["reason_code"] == "EVIDENCE.LOCALIZATION_TOPOLOGY_UNAVAILABLE"
    assert payload["localization"] is None


def test_localization_endpoint_preserves_selector_truncation_refusal() -> None:
    status_code, payload = _request_localization_endpoint(
        _LocalizationHistorian(_localization_records(), truncated=True),
        with_authority=True,
    )

    assert status_code == 200
    assert payload["disposition"] == "REFUSED_TRUNCATED"
    assert payload["reason_code"] == "SELECTION.CONDITION_HISTORY_TRUNCATED"
    assert payload["localization"] is None
    topology_authority = payload["topology_authority"]
    assert isinstance(topology_authority, dict)
    assert topology_authority["asset_id"] == "LABELER-DEMO-01"


def test_historian_condition_localization_refuses_missing_configured_policy(
    tmp_path: Path,
) -> None:
    raw = json.loads(
        (PROJECT_ROOT / "examples" / "labeler_demo_config.json").read_text(encoding="utf-8")
    )
    raw["persistence_policies"] = []
    config_path = tmp_path / "no-policy-config.json"
    config_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    authority = load_localization_topology_authority(config_path)
    historian = _LocalizationHistorian(_localization_records())

    payload = historian_condition_localization_from_query(
        historian,  # type: ignore[arg-type]
        _localization_query(),
        authority,
    )

    assert payload["schema_version"] == "linealert.configured-condition-localization.v1"
    assert payload["disposition"] == "REFUSED_POLICY_NOT_CONFIGURED"
    assert payload["reason_code"] == "POLICY.PERSISTENCE_NOT_CONFIGURED"
    assert payload["persistence_policy"] is None
    assert payload["policy_application"] is None
    assert payload["localization"] is None
    assert payload["selection"] is None
    assert historian.calls == []


def test_localization_endpoint_unavailable_uses_configured_response_schema() -> None:
    status_code, payload = _request_localization_endpoint(
        _LocalizationHistorian(_localization_records()),
        with_authority=False,
    )

    assert status_code == 503
    assert payload["schema_version"] == "linealert.configured-condition-localization.v1"
    assert payload["persistence_policy"] is None
    assert payload["policy_application"] is None
    assert payload["topology_authority"] is None
