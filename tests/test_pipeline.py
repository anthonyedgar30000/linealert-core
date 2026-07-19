from __future__ import annotations

from linealert_core import (
    DependencyEdge,
    LineAlertCore,
    TemporalRule,
    TimingStatus,
    TopologyGraph,
)


def build_core() -> LineAlertCore:
    topology = TopologyGraph(
        [
            DependencyEdge("ProductDetected", "ActuatorCommand"),
            DependencyEdge("ActuatorCommand", "ProductTransfer"),
        ]
    )
    rule = TemporalRule(
        rule_id="transfer-delay",
        start_event="ActuatorCommand",
        end_event="ProductTransfer",
        min_delay_seconds=2.0,
        max_delay_seconds=4.0,
        topology_from="ActuatorCommand",
        topology_to="ProductTransfer",
    )
    return LineAlertCore(rules=[rule], topology=topology)


def test_late_relationship_produces_bounded_recommendation(make_event) -> None:
    core = build_core()
    core.ingest(
        make_event(event_id="e-1", event_type="ActuatorCommand", seconds=0)
    )
    result = core.ingest(
        make_event(event_id="e-2", event_type="ProductTransfer", seconds=5)
    )

    assert result.timing_findings[0].status is TimingStatus.LATE
    recommendation = result.recommendations[0]
    assert recommendation.topology.upstream == "ActuatorCommand"
    assert "cause remains unresolved" in recommendation.interpretation
    assert "does not prove a root cause" in recommendation.retained_uncertainty


def test_within_envelope_does_not_create_diagnostic_action(make_event) -> None:
    core = build_core()
    core.ingest(
        make_event(event_id="e-1", event_type="ActuatorCommand", seconds=0)
    )
    result = core.ingest(
        make_event(event_id="e-2", event_type="ProductTransfer", seconds=3)
    )

    assert result.timing_findings[0].status is TimingStatus.WITHIN
    assert result.recommendations == ()


def test_correlation_ids_prevent_cross_cycle_pairing(make_event) -> None:
    core = build_core()
    core.ingest(
        make_event(
            event_id="e-1",
            event_type="ActuatorCommand",
            correlation_id="cycle-1",
            seconds=0,
        )
    )
    result = core.ingest(
        make_event(
            event_id="e-2",
            event_type="ProductTransfer",
            correlation_id="cycle-2",
            seconds=5,
        )
    )

    assert result.timing_findings == ()


def test_replay_is_deterministic(make_event) -> None:
    events = [
        make_event(event_id="e-1", event_type="ActuatorCommand", seconds=0),
        make_event(event_id="e-2", event_type="ProductTransfer", seconds=5),
    ]

    outputs = []
    for _ in range(2):
        core = build_core()
        outputs.append([core.ingest(event) for event in events])

    assert outputs[0] == outputs[1]
