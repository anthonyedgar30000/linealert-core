from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from linealert_core import ConditionRuntimeSnapshot, replay_condition_events

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_condition_runtime_starts_unconfigured() -> None:
    payload = ConditionRuntimeSnapshot().get()

    assert payload["schema_version"] == "linealert.condition-runtime.v1"
    assert payload["configured"] is False
    assert payload["running"] is False
    assert payload["measurement_count"] == 0
    assert payload["condition"] is None
    assert payload["reason_code"] == "EVIDENCE.CONDITION_RUNTIME_NOT_CONFIGURED"


def test_condition_runtime_publishes_demo_event_measurement() -> None:
    snapshot = ConditionRuntimeSnapshot()

    summary = asyncio.run(
        replay_condition_events(
            PROJECT_ROOT / "examples" / "labeler_demo_events.jsonl",
            PROJECT_ROOT / "examples" / "labeler_demo_config.json",
            PROJECT_ROOT / "examples" / "condition_signal_bindings.json",
            snapshot,
            interval_seconds=0,
        )
    )
    payload = snapshot.get()

    assert summary.measurement_count == 1
    assert payload["configured"] is True
    assert payload["running"] is False
    assert payload["source_mode"] == "deterministic_event_replay"
    assert payload["measurement_count"] == 1
    assert payload["refusal_count"] == 0
    assert payload["reason_code"] == "EVIDENCE.CONDITION_RUNTIME_COMPLETE"

    observations = payload["condition"]["condition_signals"]["observations"]
    assert len(observations) == 1
    observation = observations[0]
    assert observation["signal"] == "label_presentation_delay_ms"
    assert observation["value"] == 550.0
    assert observation["min_value"] == 50.0
    assert observation["max_value"] == 350.0
    assert observation["temporal_rule_status"] == "late"
    assert observation["clock_evidence"]["basis"] == "same_source_relative_interval"


def test_condition_runtime_rejects_negative_replay_interval() -> None:
    snapshot = ConditionRuntimeSnapshot()

    with pytest.raises(ValueError, match="finite non-negative"):
        asyncio.run(
            replay_condition_events(
                PROJECT_ROOT / "examples" / "labeler_demo_events.jsonl",
                PROJECT_ROOT / "examples" / "labeler_demo_config.json",
                PROJECT_ROOT / "examples" / "condition_signal_bindings.json",
                snapshot,
                interval_seconds=-0.1,
            )
        )


def test_condition_runtime_error_retains_prior_evidence() -> None:
    snapshot = ConditionRuntimeSnapshot()
    asyncio.run(
        replay_condition_events(
            PROJECT_ROOT / "examples" / "labeler_demo_events.jsonl",
            PROJECT_ROOT / "examples" / "labeler_demo_config.json",
            PROJECT_ROOT / "examples" / "condition_signal_bindings.json",
            snapshot,
            interval_seconds=0,
        )
    )

    snapshot.mark_error(RuntimeError("transport stopped"))
    payload = snapshot.get()

    assert payload["running"] is False
    assert payload["measurement_count"] == 1
    assert payload["condition"] is not None
    assert payload["reason_code"] == "EVIDENCE.CONDITION_RUNTIME_ERROR"
    assert payload["error"] == "RuntimeError"
