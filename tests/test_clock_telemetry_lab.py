from __future__ import annotations

import copy
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from linealert_core.clock_evidence import assess_clock_drift
from linealert_core.clock_telemetry_lab import (
    ClockStepBoundary,
    ClockStepCoverage,
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
    assert provenance.step_coverage_id == "lab-step-monitor-a-1"
    assert provenance.step_coverage_method == "SYNTHETIC_COMPLETE_STEP_NOTICE_FEED"
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
    tampered_coverage = copy.deepcopy(report["condition_signals"]["observations"][0])
    tampered_coverage["clock_evidence"]["interval_assessment"]["start_observation"][
        "telemetry_provenance"
    ]["step_coverage_until_reference"] = BASE.isoformat()
    with pytest.raises(ValueError, match="invalid condition clock"):
        measurement_from_payload(tampered_coverage)


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


def step_boundary() -> ClockStepBoundary:
    adapter = load_clock_telemetry_lab(FIXTURE)
    binding = adapter._bindings["plc-a"]
    return ClockStepBoundary(
        boundary_id="lab-step-a-1",
        binding_id=binding.binding_id,
        source_id=binding.source_id,
        clock_id=binding.clock_id,
        reference_clock_id=binding.reference_clock_id,
        reference_path=binding.reference_path,
        earliest_reference=BASE + timedelta(milliseconds=1000),
        latest_reference=BASE + timedelta(milliseconds=1050),
        observation_method="SYNTHETIC_STEP_INJECTION",
    )


def test_step_boundary_blocks_old_sample_and_requires_fresh_post_step_measurement() -> None:
    base = load_clock_telemetry_lab(FIXTURE)
    boundary = step_boundary()
    old = ClockTelemetryLabAdapter(tuple(base._bindings.values()), base._samples, (boundary,))

    assert old.project(event("before", "plc-a", "Start", 902)).observation is not None
    for timestamp_ms in (1001, 1002, 1052, 1202):
        result = old.project(event(f"blocked-{timestamp_ms}", "plc-a", "Start", timestamp_ms))
        assert result.observation is None
        assert result.refusal is not None
        assert result.refusal.reason_code == "CLOCK.STEP_WINDOW_UNQUALIFIED"
        assert result.refusal.step_boundary_ids == (boundary.boundary_id,)
    assert old.project(event("other-source", "scada-b", "End", 1200)).observation is not None

    fresh = replace(
        base._samples[0],
        sample_id="lab-offset-a-2",
        sampled_at_reference=BASE + timedelta(milliseconds=1100),
        offset_ms=20,
    )
    renewed = ClockTelemetryLabAdapter(
        tuple(base._bindings.values()), (*base._samples, fresh), (boundary,)
    )
    result = renewed.project(event("after", "plc-a", "Start", 1220))
    assert result.refusal is None and result.observation is not None
    assert result.observation.observed_at_reference == BASE + timedelta(milliseconds=1200)
    provenance = result.observation.telemetry_provenance
    assert provenance is not None
    assert provenance.sample_id == fresh.sample_id
    assert provenance.last_step_boundary_id == boundary.boundary_id
    assert provenance.last_step_earliest_reference == boundary.earliest_reference
    assert provenance.last_step_latest_reference == boundary.latest_reference
    assert provenance.last_step_observation_method == boundary.observation_method

    consumer = LiveConditionConsumer(
        LineAlertCore(
            rules=[
                TemporalRule(
                    rule_id="step-delay",
                    start_event="Start",
                    end_event="End",
                    min_delay_seconds=0.1,
                    max_delay_seconds=0.6,
                    topology_from="Start",
                    topology_to="End",
                )
            ],
            topology=TopologyGraph([DependencyEdge("Start", "End")]),
        ),
        (
            TimingConditionBinding(
                signal_name="step_delay_ms",
                rule_id="step-delay",
                semantic="lab_delay",
                scope="synthetic_lab",
                max_combined_uncertainty_ms=10,
            ),
        ),
    )
    first, _ = renewed.annotate(envelope(event("after", "plc-a", "Start", 1220)))
    second, _ = renewed.annotate(envelope(event("end-after", "scada-b", "End", 1497)))
    consumer.consume(first)
    consumed = consumer.consume(second)
    assert len(consumed.measurements) == 1
    payload = live_condition_summary_to_dict(consumer.summary())["condition_signals"][
        "observations"
    ][0]
    rebuilt = measurement_from_payload(payload)
    retained = rebuilt.clock_evidence.interval_assessment.start_observation.telemetry_provenance
    assert retained == provenance
    tampered = copy.deepcopy(payload)
    tampered["clock_evidence"]["interval_assessment"]["start_observation"][
        "telemetry_provenance"
    ]["last_step_latest_reference"] = (BASE + timedelta(milliseconds=1300)).isoformat()
    with pytest.raises(ValueError, match="invalid condition clock"):
        measurement_from_payload(tampered)


def test_step_boundary_identity_and_fixture_validation(tmp_path: Path) -> None:
    base = load_clock_telemetry_lab(FIXTURE)
    boundary = step_boundary()
    bindings = tuple(base._bindings.values())
    conflict = replace(boundary, reference_path=("lab-reference-1", "other", "clock-plc-a"))
    result = ClockTelemetryLabAdapter(bindings, base._samples, (conflict,)).project(
        event("conflict", "plc-a", "Start", 1202)
    )
    assert result.refusal is not None
    assert result.refusal.reason_code == "CLOCK.STEP_BINDING_CONFLICT"
    assert result.refusal.step_boundary_ids == (conflict.boundary_id,)
    with pytest.raises(ClockTelemetryLabError, match="unique"):
        ClockTelemetryLabAdapter(bindings, base._samples, (boundary, boundary))

    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["step_boundaries"] = [
        {
            "boundary_id": boundary.boundary_id,
            "binding_id": boundary.binding_id,
            "source_id": boundary.source_id,
            "clock_id": boundary.clock_id,
            "reference_clock_id": boundary.reference_clock_id,
            "reference_path": list(boundary.reference_path),
            "earliest_reference": boundary.earliest_reference.isoformat(),
            "latest_reference": boundary.latest_reference.isoformat(),
            "observation_method": boundary.observation_method,
        }
    ]
    fixture = tmp_path / "step.json"
    fixture.write_text(json.dumps(raw), encoding="utf-8")
    loaded = load_clock_telemetry_lab(fixture)
    assert loaded.project(event("later", "plc-a", "Start", 1202)).refusal.reason_code == (
        "CLOCK.STEP_WINDOW_UNQUALIFIED"
    )
    raw["step_boundaries"][0]["source_classification"] = "physical_plant"
    fixture.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ClockTelemetryLabError, match="invalid lab clock fixture"):
        load_clock_telemetry_lab(fixture)


def test_strict_step_coverage_refuses_missing_gap_degraded_overlap_and_conflict() -> None:
    base = load_clock_telemetry_lab(FIXTURE)
    bindings = tuple(base._bindings.values())
    sample = base._samples[0]
    covered = base._step_coverages[0]
    target = event("start", "plc-a", "Start", 2)

    def refusal(*coverages: ClockStepCoverage) -> str:
        adapter = ClockTelemetryLabAdapter(
            bindings, (sample,), step_coverages=coverages, require_step_coverage=True
        )
        result = adapter.project(target)
        assert result.observation is None and result.refusal is not None
        return result.refusal.reason_code

    assert refusal() == "CLOCK.STEP_COVERAGE_MISSING"
    assert refusal(replace(covered, coverage_start_reference=BASE)) == (
        "CLOCK.STEP_COVERAGE_GAP"
    )
    assert refusal(replace(covered, coverage_until_reference=BASE + timedelta(milliseconds=1))) == (
        "CLOCK.STEP_COVERAGE_GAP"
    )
    assert refusal(replace(covered, monitor_state="DEGRADED")) == (
        "CLOCK.STEP_COVERAGE_UNQUALIFIED"
    )
    assert refusal(covered, replace(covered, coverage_id="overlapping-monitor")) == (
        "CLOCK.STEP_COVERAGE_AMBIGUOUS"
    )
    overlapping = ClockTelemetryLabAdapter(
        bindings,
        (sample,),
        step_coverages=(covered, replace(covered, coverage_id="overlapping-monitor")),
        require_step_coverage=True,
    ).project(target)
    assert overlapping.refusal is not None
    assert overlapping.refusal.step_coverage_ids == (
        "lab-step-monitor-a-1",
        "overlapping-monitor",
    )
    assert refusal(replace(covered, configuration_version="other-config")) == (
        "CLOCK.STEP_COVERAGE_BINDING_CONFLICT"
    )
    assert refusal(replace(covered, calibration_id="other-calibration")) == (
        "CLOCK.STEP_COVERAGE_BINDING_CONFLICT"
    )
    with pytest.raises(ClockTelemetryLabError, match="unique"):
        ClockTelemetryLabAdapter(
            bindings,
            (sample,),
            step_coverages=(covered, covered),
            require_step_coverage=True,
        )
    with pytest.raises(ClockTelemetryLabError, match="explicit strict mode"):
        ClockTelemetryLabAdapter(bindings, (sample,), step_coverages=(covered,))


def test_strict_step_coverage_and_fresh_sample_after_boundary() -> None:
    base = load_clock_telemetry_lab(FIXTURE)
    boundary = step_boundary()
    fresh = replace(
        base._samples[0],
        sample_id="fresh-after-step",
        sampled_at_reference=BASE + timedelta(milliseconds=1100),
        offset_ms=20,
    )
    adapter = ClockTelemetryLabAdapter(
        tuple(base._bindings.values()),
        (*base._samples, fresh),
        step_boundaries=(boundary,),
        step_coverages=base._step_coverages,
        require_step_coverage=True,
    )
    result = adapter.project(event("after", "plc-a", "Start", 1220))
    assert result.refusal is None and result.observation is not None
    provenance = result.observation.telemetry_provenance
    assert provenance is not None
    assert provenance.sample_id == fresh.sample_id
    assert provenance.last_step_boundary_id == boundary.boundary_id
    assert provenance.step_coverage_id == "lab-step-monitor-a-1"


def test_strict_lab_fixture_requires_explicit_coverage(tmp_path: Path) -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["step_coverages"] = []
    fixture = tmp_path / "no-coverage.json"
    fixture.write_text(json.dumps(raw), encoding="utf-8")
    result = load_clock_telemetry_lab(fixture).project(event("start", "plc-a", "Start", 2))
    assert result.refusal is not None
    assert result.refusal.reason_code == "CLOCK.STEP_COVERAGE_MISSING"
    covered = json.loads(FIXTURE.read_text(encoding="utf-8"))["step_coverages"][0]
    raw["step_coverages"] = [{**covered, "source_classification": "physical_plant"}]
    fixture.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ClockTelemetryLabError, match="invalid lab clock fixture"):
        load_clock_telemetry_lab(fixture)
