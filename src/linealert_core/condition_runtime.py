"""Runtime publication of governed live-condition evidence."""

from __future__ import annotations

import asyncio
import json
import math
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .condition_projection import load_condition_signal_bindings
from .live_condition import (
    LiveConditionConsumer,
    LiveConditionSummary,
    live_condition_summary_to_dict,
)
from .replay import build_core_from_config, load_events
from .simulator import DeterministicStreamSimulator


class ConditionRuntimeSnapshot:
    """Thread-safe API snapshot for the latest condition-stream state."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._payload = self._unconfigured_payload()

    @staticmethod
    def _unconfigured_payload() -> dict[str, Any]:
        return {
            "schema_version": "linealert.condition-runtime.v1",
            "configured": False,
            "running": False,
            "source_mode": "unconfigured",
            "measurement_count": 0,
            "refusal_count": 0,
            "reason_code": "EVIDENCE.CONDITION_RUNTIME_NOT_CONFIGURED",
            "claim_boundary": (
                "No condition-event stream is configured. Telemetry and replay evidence must not "
                "be promoted into condition measurements implicitly."
            ),
            "condition": None,
        }

    def get(self) -> dict[str, Any]:
        """Return an immutable JSON-compatible copy of the current API payload."""

        with self._lock:
            return json.loads(json.dumps(self._payload))

    def update(
        self,
        summary: LiveConditionSummary,
        *,
        source_mode: str,
        running: bool,
    ) -> dict[str, Any]:
        """Publish one exact consumer summary without upgrading its claim boundary."""

        condition = live_condition_summary_to_dict(summary)
        payload = {
            "schema_version": "linealert.condition-runtime.v1",
            "configured": True,
            "running": running,
            "source_mode": source_mode,
            "updated_at": datetime.now(UTC).isoformat(),
            "measurement_count": summary.measurement_count,
            "refusal_count": summary.refusal_count,
            "reason_code": (
                "EVIDENCE.CONDITION_RUNTIME_RUNNING"
                if running
                else "EVIDENCE.CONDITION_RUNTIME_COMPLETE"
            ),
            "claim_boundary": condition["claim_boundary"],
            "condition": condition,
        }
        immutable = json.loads(json.dumps(payload))
        with self._lock:
            self._payload = immutable
            return json.loads(json.dumps(immutable))

    def mark_error(self, exc: Exception) -> dict[str, Any]:
        """Retain prior evidence while making runtime failure explicit."""

        with self._lock:
            payload = json.loads(json.dumps(self._payload))
            payload.update(
                {
                    "running": False,
                    "updated_at": datetime.now(UTC).isoformat(),
                    "reason_code": "EVIDENCE.CONDITION_RUNTIME_ERROR",
                    "error": type(exc).__name__,
                }
            )
            self._payload = payload
            return json.loads(json.dumps(payload))


async def replay_condition_events(
    events_path: str | Path,
    config_path: str | Path,
    bindings_path: str | Path,
    snapshot: ConditionRuntimeSnapshot,
    *,
    interval_seconds: float = 0.1,
    clock_quality: str = "synchronized",
    session_id: str = "condition-runtime-replay",
) -> LiveConditionSummary:
    """Publish a deterministic event replay through the same incremental condition path."""

    if not math.isfinite(interval_seconds) or interval_seconds < 0:
        raise ValueError("condition replay interval must be a finite non-negative number")

    events = load_events(events_path)
    bindings = load_condition_signal_bindings(bindings_path)
    consumer = LiveConditionConsumer(build_core_from_config(config_path), bindings)
    source_mode = "deterministic_event_replay"
    snapshot.update(consumer.summary(), source_mode=source_mode, running=True)

    simulator = DeterministicStreamSimulator(
        events=events,
        session_id=session_id,
        ingestion_delay_seconds=interval_seconds,
        clock_quality=clock_quality,
        transport_attributes={
            "source": "condition-runtime",
            "source_mode": source_mode,
        },
    )
    try:
        for envelope in simulator:
            consumer.consume(envelope)
            snapshot.update(consumer.summary(), source_mode=source_mode, running=True)
            if interval_seconds:
                await asyncio.sleep(interval_seconds)
    except Exception as exc:
        snapshot.mark_error(exc)
        raise

    summary = consumer.summary()
    snapshot.update(summary, source_mode=source_mode, running=False)
    return summary
