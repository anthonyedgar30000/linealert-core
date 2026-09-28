from __future__ import annotations

import copy
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from linealert_core.clock_evidence import assess_clock_drift
from linealert_core.clock_telemetry_lab import (
    ClockTelemetryLabAdapter,
    ClockTelemetryLabError,
    load_clock_telemetry_lab,
)
from linealert_core.condition_projection import TimingConditionBinding
from linealert_core.events import MachineEvent
from linealert_core.historian_service import measurement_from_payload
from linealert_core.live_condition import LiveConditionConsumer, live_condition_summary_to_dict
from linealert_core.pipeline import LineAlertCore
from linealert_core.streaming import StreamEnvelope
from linealert_core.timing import TemporalRule
from linealert_core.topology import DependencyEdge, TopologyGraph

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "clock_telemetry_lab_v1.json"
BASE = datetime(2026, 9, 28, 19, tzinfo=UTC)


def event(name: str, source: str, kind: str, milliseconds: float) -> MachineEvent:
    return MachineEvent(
        event_id=name,
        source_id=source,
        asset_id="LAB-01",
        component_id="lab-station",
        event_type=kind,
        timestamp=BASE + timedelta(milliseconds=milliseconds),
        correlation_id="cycle-1",
    )


def envelope(e: MachineEvent) -> StreamEnvelope:
    return StreamEnvelope(
        session_id=f"session-{e.source_id}",
        sequence_number=0,
        received_at=e.timestamp + timedelta(milliseconds=10),
        event=e,
        clock_quality="synchronized",
    )


def test_fixture_projects_exact_source_clock_with_holdover_uncertainty() -> None:
    adapter = load_clock_telemetry_lab(FIXTURE)
    first = event("start", "plc-a", "Start", 2)
    second = event("end", "scada-b", "End", 303)
    start_env, start_projection = adapter.annotate(envelope(first))
    end_env, end_projection = adapter.annotate(envelope(second))
    assert start_projection.refusal is None
    assert end_projection.refusal is None
    assert start_env.event is first
    assert start_env.clock_quality == "synchronized"
    assert start_env.clock_observation is not None
    assert end_env.clock_observation is not None
    assert start_env.clock_observation.observed_at_reference == BASE
    assert end_env.clock_observation.observed_at_reference == BASE + timedelta(milliseconds=306)
    provenance = start_env.clock_observation.telemetry_provenance
    assert provenance is not None
    assert provenance.sample_id == "lab-offset-a-1"
    assert provenance.reference_path == ("lab-reference-1", "lab-switch-1", "clock-plc-a")
    assert provenance.configuration_version == "synthetic-config-1"
    assert provenance.source_classification == "synthetic_lab_telemetry"
    assert provenance.drift_allowance_ms > 0
    assert start_env.clock_observation.uncertainty_ms > 2

    core = LineAlertCore(
        rules=[
            TemporalRule(
                rule_id="lab-delay",
                start_event="Start",
                end_event="End",
                min_delay_seconds=0.1,
                max_delay_seconds=0.6,
                topology_from="Start",
                topology_to="End",
            )
        ],
        topology=TopologyGraph([DependencyEdge("Start", "End")]),
    )
    binding = TimingConditionBinding(
        signal_name="lab_delay_ms",
        rule_id="lab-delay",
        semantic="lab_delay",
        scope="synthetic_lab",
        max_combined_uncertainty_ms=10,
    )
    consumer = LiveConditionConsumer(core, (binding,))
    consumer.consume(start_env)
    result = consumer.consume(end_env)
    assert len(result.measurements) == 1
    assessment = result.measurements[0].clock_evidence.interval_assessment
    assert assessment is not None
    assert assessment.raw_delay_ms == pytest.approx(301)
    assert assessment.estimated_delay_ms == pytest.approx(306)
    report = live_condition_summary_to_dict(consumer.summary())
    rebuilt = measurement_from_payload(report["condition_signals"]["observations"][0])
    assert rebuilt.clock_evidence.interval_assessment == assessment
    tampered = copy.deepcopy(report["condition_signals"]["observations"][0])
    provenance = tampered["clock_evidence"]["interval_assessment"]["start_observation"][
        "telemetry_provenance"
    ]
    provenance["drift_allowance_ms"] = 0
    with pytest.raises(ValueError, match="invalid condition clock"):
        measurement_from_payload(tampered)


@pytest.mark.parametrize(
    "change,reason",
    [
        (
            {"reference_path": ("lab-reference-1", "other-switch", "clock-plc-a")},
            "CLOCK.BINDING_CONFLICT",
        ),
        ({"configuration_version": "different-config"}, "CLOCK.BINDING_CONFLICT"),
        ({"calibration_id": "different-cal"}, "CLOCK.BINDING_CONFLICT"),
        ({"synchronization_state": "DEGRADED"}, "CLOCK.SYNC_UNQUALIFIED"),
        (
            {"valid_until_reference": BASE - timedelta(milliseconds=1)},
            "CLOCK.SAMPLE_OUTSIDE_VALIDITY",
        ),
    ],
)
def test_conflicting_degraded_or_expired_sample_refuses(change, reason: str) -> None:
    adapter = load_clock_telemetry_lab(FIXTURE)
    sample = replace(adapter._samples[0], **change)
    modified = ClockTelemetryLabAdapter(
        tuple(adapter._bindings.values()), (sample, adapter._samples[1])
    )
    result = modified.project(event("start", "plc-a", "Start", 2))
    assert result.observation is None
    assert result.refusal is not None and result.refusal.reason_code == reason


def test_missing_stale_and_overlapping_samples_refuse_without_latest_wins() -> None:
    adapter = load_clock_telemetry_lab(FIXTURE)
    unbound = adapter.project(event("unbound", "other-source", "Start", 2))
    assert unbound.refusal is not None and unbound.refusal.reason_code == "CLOCK.BINDING_MISSING"
    missing = ClockTelemetryLabAdapter(tuple(adapter._bindings.values()), ())
    assert missing.project(event("start", "plc-a", "Start", 2)).refusal.reason_code == (
        "CLOCK.SAMPLE_MISSING"
    )
    stale = adapter.project(event("late", "plc-a", "Start", 7002))
    assert stale.refusal is not None
    assert stale.refusal.reason_code == "CLOCK.SAMPLE_OUTSIDE_VALIDITY"
    duplicate = replace(adapter._samples[0], sample_id="second-qualified-sample")
    overlap = ClockTelemetryLabAdapter(
        tuple(adapter._bindings.values()), (*adapter._samples, duplicate)
    )
    result = overlap.project(event("start", "plc-a", "Start", 2))
    assert result.refusal is not None
    assert result.refusal.reason_code == "CLOCK.SAMPLE_AMBIGUOUS"
    assert set(result.refusal.sample_ids) == {"lab-offset-a-1", "second-qualified-sample"}


def test_invalid_lab_fixture_or_existing_clock_observation_fails_closed(tmp_path: Path) -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["classification"] = "physical_plant"
    path = tmp_path / "clock.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ClockTelemetryLabError, match="synthetic_lab_only"):
        load_clock_telemetry_lab(path)
    adapter = load_clock_telemetry_lab(FIXTURE)
    annotated, _ = adapter.annotate(envelope(event("start", "plc-a", "Start", 2)))
    with pytest.raises(ClockTelemetryLabError, match="cannot be overwritten"):
        adapter.annotate(annotated)


def test_resolved_lab_offset_series_yields_drift_and_step_candidates() -> None:
    base_adapter = load_clock_telemetry_lab(FIXTURE)
    binding = base_adapter._bindings["plc-a"]
    template = base_adapter._samples[0]

    def project_series(offsets: tuple[float, ...]):
        samples = tuple(
            replace(
                template,
                sample_id=f"sample-{i}",
                sampled_at_reference=BASE + timedelta(seconds=i - 0.2),
                valid_until_reference=BASE + timedelta(seconds=i + 0.2),
                offset_ms=offset,
                uncertainty_ms=0.001,
                maximum_drift_ppm=0,
            )
            for i, offset in enumerate(offsets)
        )
        adapter = ClockTelemetryLabAdapter((binding,), samples)
        projected = tuple(
            adapter.project(
                event(
                    f"event-{i}",
                    "plc-a",
                    "Start",
                    i * 1000 + offset,
                )
            )
            for i, offset in enumerate(offsets)
        )
        assert all(result.refusal is None for result in projected)
        return tuple(result.observation for result in projected)

    drift = assess_clock_drift(project_series((0, 0.02, 0.04, 0.06)), minimum_rate_ppm=10)
    assert drift.disposition == "DRIFT_CANDIDATE"
    step = assess_clock_drift(project_series((0, 0, 200, 200)), minimum_rate_ppm=10)
    assert step.disposition == "STEP_CANDIDATE"
