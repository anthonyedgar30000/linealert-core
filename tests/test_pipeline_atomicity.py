from __future__ import annotations

import pytest

from linealert_core import (
    DependencyEdge,
    LineAlertCore,
    TemporalRule,
    TimingMonitor,
    TimingStatus,
    TopologyGraph,
)


def build_rule() -> TemporalRule:
    return TemporalRule(
        rule_id="transfer-delay",
        start_event="ActuatorCommand",
        end_event="ProductTransfer",
        min_delay_seconds=1.0,
        max_delay_seconds=4.0,
        topology_from="ActuatorCommand",
        topology_to="ProductTransfer",
    )


def build_core() -> LineAlertCore:
    topology = TopologyGraph(
        [
            DependencyEdge("ProductDetected", "ActuatorCommand"),
            DependencyEdge("ActuatorCommand", "ProductTransfer"),
        ]
    )
    return LineAlertCore(rules=[build_rule()], topology=topology)


@pytest.mark.xfail(
    strict=True,
    reason="FW-02: negative timing currently consumes the matching start",
)
def test_negative_end_timestamp_does_not_consume_matching_start(make_event) -> None:
    monitor = TimingMonitor([build_rule()])
    monitor.handle(
        make_event(
            event_id="atomic-3-start",
            event_type="ActuatorCommand",
            seconds=2,
        )
    )

    with pytest.raises(ValueError, match="precedes start event"):
        monitor.handle(
            make_event(
                event_id="atomic-3-invalid-end",
                event_type="ProductTransfer",
                seconds=1,
            )
        )

    findings = monitor.handle(
        make_event(
            event_id="atomic-3-valid-end",
            event_type="ProductTransfer",
            seconds=4,
        )
    )

    assert len(findings) == 1
    assert findings[0].delay_seconds == 2.0
    assert findings[0].status is TimingStatus.WITHIN


@pytest.mark.xfail(
    strict=True,
    reason="FW-04: diagnostic failure currently commits the end-event transition",
)
def test_diagnostic_failure_does_not_commit_end_event_transition(
    make_event,
    monkeypatch,
) -> None:
    core = build_core()
    core.ingest(
        make_event(
            event_id="atomic-4-start",
            event_type="ActuatorCommand",
            seconds=0,
        )
    )
    end = make_event(
        event_id="atomic-4-end",
        event_type="ProductTransfer",
        seconds=5,
    )
    original_recommend = core.diagnostics.recommend

    def fail_recommend(_finding):
        raise RuntimeError("bounded diagnostic failure")

    monkeypatch.setattr(core.diagnostics, "recommend", fail_recommend)
    with pytest.raises(RuntimeError, match="bounded diagnostic failure"):
        core.ingest(end)

    monkeypatch.setattr(core.diagnostics, "recommend", original_recommend)
    retry = core.ingest(end)

    assert retry.receipt.duplicate is False
    assert len(retry.timing_findings) == 1
    assert retry.timing_findings[0].status is TimingStatus.LATE
    assert len(retry.recommendations) == 1
