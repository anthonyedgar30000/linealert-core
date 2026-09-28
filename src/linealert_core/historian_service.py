"""Shared TimescaleDB historian service for LineAlert dashboard views.

This sidecar observes already-published bridge evidence and persists it after the
core/stream path has completed. It never participates in equipment control or
in the deterministic core transaction.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen

from .condition_projection import ConditionSignalObservation
from .functional_temporal import (
    EpistemicState,
    EvidenceValidity,
    TemporalCoverage,
    TransitionDisposition,
)
from .historian import (
    FunctionalTemporalHistoryRecord,
    FunctionalTemporalRecordKind,
    HistorianError,
    HistorianOperatingContext,
    TimescaleHistorian,
)
from .live_condition import LiveClockEvidence, LiveConditionMeasurement


class HistorianServiceStatus:
    """Thread-safe status exposed to both dashboard views."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._payload: dict[str, Any] = {
            "schema_version": "linealert.historian-service-status.v1",
            "connected": False,
            "source_available": False,
            "reason_code": "EVIDENCE.HISTORIAN_STARTING",
        }

    def update(self, **values: Any) -> None:
        with self._lock:
            self._payload.update(values)
            self._payload["updated_at"] = datetime.now(UTC).isoformat()

    def get(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._payload))


def _fetch_json(url: str, *, timeout: float = 1.5) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - local configured source
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("historian source response must be a JSON object")
    return payload


def measurement_from_payload(raw: dict[str, Any]) -> LiveConditionMeasurement:
    """Rebuild the already-admitted condition payload without reinterpreting it."""

    clock_raw = raw.get("clock_evidence")
    if not isinstance(clock_raw, dict):
        raise ValueError("condition observation is missing clock evidence")
    required = (
        "signal",
        "value",
        "unit",
        "min_value",
        "max_value",
        "asset_id",
        "rule_id",
        "correlation_id",
        "source_timestamp",
        "start_timestamp",
        "end_timestamp",
        "topology_from",
        "topology_to",
        "temporal_rule_status",
        "semantic",
        "scope",
        "relationship_id",
        "observation_id",
        "quality",
        "reason_code",
    )
    missing = [name for name in required if raw.get(name) is None]
    if missing:
        raise ValueError(f"condition observation missing fields: {', '.join(missing)}")
    observation = ConditionSignalObservation(
        signal_name=str(raw["signal"]),
        value=float(raw["value"]),
        unit=str(raw["unit"]),
        min_value=float(raw["min_value"]),
        max_value=float(raw["max_value"]),
        asset_id=str(raw["asset_id"]),
        rule_id=str(raw["rule_id"]),
        correlation_id=str(raw["correlation_id"]),
        source_timestamp=str(raw["source_timestamp"]),
        start_timestamp=str(raw["start_timestamp"]),
        end_timestamp=str(raw["end_timestamp"]),
        topology_from=str(raw["topology_from"]),
        topology_to=str(raw["topology_to"]),
        temporal_rule_status=str(raw["temporal_rule_status"]),
        semantic=str(raw["semantic"]),
        scope=str(raw["scope"]),
        relationship_id=str(raw["relationship_id"]),
        observation_id=str(raw["observation_id"]),
        quality=str(raw["quality"]),
        reason_code=str(raw["reason_code"]),
        start_event_id=raw.get("start_event_id"),
        end_event_id=raw.get("end_event_id"),
        start_source_id=raw.get("start_source_id"),
        end_source_id=raw.get("end_source_id"),
    )
    clock = LiveClockEvidence(
        start_clock_quality=str(clock_raw.get("start_clock_quality", "unknown")),
        end_clock_quality=str(clock_raw.get("end_clock_quality", "unknown")),
        basis=str(clock_raw.get("basis", "unknown")),
        retained_uncertainty=str(clock_raw.get("retained_uncertainty", "")),
    )
    return LiveConditionMeasurement(observation=observation, clock_evidence=clock)


def functional_temporal_record_from_payload(
    raw: dict[str, Any],
) -> FunctionalTemporalHistoryRecord:
    """Validate one already-evaluated functional-temporal historian payload."""

    context_raw = raw.get("operating_context")
    if not isinstance(context_raw, dict):
        raise ValueError("functional-temporal record requires operating_context")
    required_context = (
        "asset_id",
        "component_id",
        "profile_id",
        "operating_mode",
        "configuration_version",
        "firmware_version",
        "calibration_id",
        "sampling_profile_id",
    )
    missing_context = [
        name for name in required_context if not str(context_raw.get(name, "")).strip()
    ]
    if missing_context:
        raise ValueError("operating_context missing fields: " + ", ".join(missing_context))

    required = (
        "observed_at",
        "record_id",
        "episode_id",
        "cycle_id",
        "record_kind",
        "epistemic_state",
        "evidence_validity",
        "temporal_coverage",
        "source_id",
    )
    missing = [name for name in required if not str(raw.get(name, "")).strip()]
    if missing:
        raise ValueError("functional-temporal record missing fields: " + ", ".join(missing))
    try:
        observed_at = datetime.fromisoformat(str(raw["observed_at"]).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("observed_at must be ISO 8601") from exc

    context_tags = context_raw.get("context_tags", {})
    if not isinstance(context_tags, dict):
        raise ValueError("operating_context.context_tags must be an object")
    clock_evidence = raw.get("clock_evidence", {})
    details = raw.get("details", {})
    if not isinstance(clock_evidence, dict) or not isinstance(details, dict):
        raise ValueError("clock_evidence and details must be objects")

    evidence_ids = raw.get("evidence_ids", [])
    reasons = raw.get("reasons", [])
    if not isinstance(evidence_ids, list) or not isinstance(reasons, list):
        raise ValueError("evidence_ids and reasons must be arrays")
    if any(not isinstance(item, str) or not item.strip() for item in evidence_ids):
        raise ValueError("evidence_ids must contain non-empty strings")
    if any(not isinstance(item, str) or not item.strip() for item in reasons):
        raise ValueError("reasons must contain non-empty strings")
    try:
        return FunctionalTemporalHistoryRecord(
            observed_at=observed_at,
            record_id=raw["record_id"],
            episode_id=raw["episode_id"],
            cycle_id=raw["cycle_id"],
            record_kind=FunctionalTemporalRecordKind(raw["record_kind"]),
            state=EpistemicState(raw["epistemic_state"]),
            validity=EvidenceValidity(raw["evidence_validity"]),
            coverage=TemporalCoverage(raw["temporal_coverage"]),
            source_id=raw["source_id"],
            operating_context=HistorianOperatingContext(
                asset_id=context_raw["asset_id"],
                component_id=context_raw["component_id"],
                profile_id=context_raw["profile_id"],
                operating_mode=context_raw["operating_mode"],
                configuration_version=context_raw["configuration_version"],
                firmware_version=context_raw["firmware_version"],
                calibration_id=context_raw["calibration_id"],
                sampling_profile_id=context_raw["sampling_profile_id"],
                recipe_id=_optional_text(context_raw.get("recipe_id")),
                product_id=_optional_text(context_raw.get("product_id")),
                context_tags=context_tags,
            ),
            phase_id=_optional_text(raw.get("phase_id")),
            transition_id=_optional_text(raw.get("transition_id")),
            from_phase_id=_optional_text(raw.get("from_phase_id")),
            to_phase_id=_optional_text(raw.get("to_phase_id")),
            trigger_event_id=_optional_text(raw.get("trigger_event_id")),
            requirement_id=_optional_text(raw.get("requirement_id")),
            transition_disposition=(
                TransitionDisposition(raw["transition_disposition"])
                if raw.get("transition_disposition") is not None
                else None
            ),
            evidence_ids=tuple(evidence_ids),
            reasons=tuple(reasons),
            clock_evidence=clock_evidence,
            details=details,
        )
    except (HistorianError, ValueError) as exc:
        raise ValueError(str(exc)) from exc


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional identity fields must be strings when supplied")
    return value if value.strip() else None


def persist_published_evidence(
    source_base_url: str,
    historian: TimescaleHistorian,
    status: HistorianServiceStatus,
    *,
    episode_id: str,
) -> None:
    """Poll current bridge publications and idempotently retain them."""

    telemetry = _fetch_json(f"{source_base_url.rstrip('/')}/api/telemetry")
    historian.record_machine_observation(telemetry)

    condition_runtime = _fetch_json(f"{source_base_url.rstrip('/')}/api/condition")
    source_mode = str(condition_runtime.get("source_mode", "unknown"))
    condition = condition_runtime.get("condition")
    observations: list[dict[str, Any]] = []
    if isinstance(condition, dict):
        signals = condition.get("condition_signals")
        if isinstance(signals, dict) and isinstance(signals.get("observations"), list):
            observations = [item for item in signals["observations"] if isinstance(item, dict)]
    for raw in observations:
        operating_context = raw.get("operating_context")
        if operating_context is not None and not isinstance(operating_context, dict):
            raise ValueError("condition operating_context must be an object")
        historian.record_condition_measurement(
            measurement_from_payload(raw),
            episode_id=episode_id,
            source_mode=source_mode,
            cycle_id=_optional_text(raw.get("cycle_id")),
            phase_id=_optional_text(raw.get("phase_id")),
            operating_context=operating_context,
        )
    status.update(
        connected=True,
        source_available=True,
        reason_code="EVIDENCE.HISTORIAN_PERSISTING",
        latest_condition_count=len(observations),
        source_mode=source_mode,
    )


def poll_published_evidence(
    source_base_url: str,
    historian: TimescaleHistorian,
    status: HistorianServiceStatus,
    *,
    episode_id: str,
    interval_seconds: float,
) -> None:
    while True:
        try:
            persist_published_evidence(
                source_base_url,
                historian,
                status,
                episode_id=episode_id,
            )
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, HistorianError) as exc:
            status.update(
                connected=True,
                source_available=False,
                reason_code="EVIDENCE.HISTORIAN_SOURCE_UNAVAILABLE",
                error=type(exc).__name__,
            )
        time.sleep(interval_seconds)


def handler_for(
    historian: TimescaleHistorian,
    status: HistorianServiceStatus,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, payload: dict[str, Any], *, status_code: int = 200) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            request = urlparse(self.path)
            query = parse_qs(request.query)
            try:
                limit = int(query.get("limit", ["240"])[0])
            except ValueError:
                limit = 240
            try:
                if request.path == "/api/status":
                    self._send_json(status.get())
                    return
                if request.path == "/api/history/conditions":
                    self._send_json(
                        historian.condition_history(
                            limit=limit,
                            asset_id=query.get("asset_id", [None])[0],
                            relationship_id=query.get("relationship_id", [None])[0],
                            episode_id=query.get("episode_id", [None])[0],
                        )
                    )
                    return
                if request.path == "/api/history/observations":
                    self._send_json(
                        historian.observation_history(
                            limit=limit,
                            asset_id=query.get("asset_id", [None])[0],
                        )
                    )
                    return
                if request.path == "/api/history/functional-temporal":
                    self._send_json(
                        historian.functional_temporal_history(
                            limit=limit,
                            asset_id=query.get("asset_id", [None])[0],
                            episode_id=query.get("episode_id", [None])[0],
                            cycle_id=query.get("cycle_id", [None])[0],
                            phase_id=query.get("phase_id", [None])[0],
                            record_kind=query.get("record_kind", [None])[0],
                        )
                    )
                    return
                episode_prefix = "/api/history/episodes/"
                if request.path.startswith(episode_prefix):
                    episode_id = unquote(request.path[len(episode_prefix) :])
                    if not episode_id:
                        self._send_json({"error": "episode ID is required"}, status_code=400)
                        return
                    self._send_json(historian.episode(episode_id, limit=limit))
                    return
                self._send_json({"error": "not found"}, status_code=404)
            except HistorianError as exc:
                self._send_json({"error": str(exc)}, status_code=503)

        def do_POST(self) -> None:  # noqa: N802
            request_path = urlparse(self.path).path
            if request_path not in {"/api/outcomes", "/api/functional-temporal"}:
                self._send_json({"error": "not found"}, status_code=404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("request body must be a JSON object")
                if request_path == "/api/functional-temporal":
                    record = functional_temporal_record_from_payload(payload)
                    persisted = historian.record_functional_temporal_evidence(record)
                    self._send_json(
                        {
                            "schema_version": ("linealert.historian.functional-temporal-write.v1"),
                            "persisted": True,
                            "record": persisted,
                            "claim_boundary": (
                                "Persisted phase and requirement evidence does not by itself "
                                "prove physical root cause, verified physical state, or "
                                "authorized equipment action."
                            ),
                        },
                        status_code=201,
                    )
                    return
                outcome = historian.record_outcome(payload)
                self._send_json(
                    {
                        "schema_version": "linealert.historian.outcome-write.v1",
                        "persisted": True,
                        "outcome": outcome,
                        "claim_boundary": (
                            "Recorded operational outcome and verification evidence do not by "
                            "themselves prove physical root cause or predictive validity."
                        ),
                    },
                    status_code=201,
                )
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError, HistorianError) as exc:
                self._send_json({"error": str(exc)}, status_code=400)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--source-base-url", default="http://127.0.0.1:8765")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    parser.add_argument("--episode-id", default="condition-runtime-replay")
    args = parser.parse_args()
    if args.poll_seconds <= 0:
        parser.error("--poll-seconds must be greater than zero")

    historian = TimescaleHistorian(args.dsn)
    status = HistorianServiceStatus()
    status.update(connected=True, reason_code="EVIDENCE.HISTORIAN_CONNECTED")
    poll_thread = threading.Thread(
        target=poll_published_evidence,
        args=(args.source_base_url, historian, status),
        kwargs={"episode_id": args.episode_id, "interval_seconds": args.poll_seconds},
        daemon=True,
    )
    poll_thread.start()

    server = ThreadingHTTPServer((args.host, args.port), handler_for(historian, status))
    print(f"LineAlert shared historian: http://{args.host}:{args.port}")
    print(f"Condition history: http://{args.host}:{args.port}/api/history/conditions")
    print(f"Observation history: http://{args.host}:{args.port}/api/history/observations")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
    finally:
        historian.close()


if __name__ == "__main__":
    main()
