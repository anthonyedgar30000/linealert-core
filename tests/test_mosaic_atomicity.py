from __future__ import annotations

import pytest

from linealert_core import (
    FusionMosaic,
    Subscription,
    TemporalRule,
    TimingFinding,
    TimingMonitor,
)


def test_mosaic_handler_failure_does_not_commit_event_identity(make_event) -> None:
    calls: list[str] = []
    mosaic = FusionMosaic()

    def handler(event):
        calls.append(event.event_id)
        if len(calls) == 1:
            raise RuntimeError("bounded handler failure")
        return ()

    mosaic.register(
        Subscription(
            name="deterministic-handler",
            event_types=frozenset({"ActuatorCommand"}),
            handler=handler,
        )
    )
    event = make_event(event_id="atomic-1", event_type="ActuatorCommand")

    with pytest.raises(RuntimeError, match="bounded handler failure"):
        mosaic.publish(event)

    retry = mosaic.publish(event)

    assert retry.duplicate is False
    assert retry.delivered_to == ("deterministic-handler",)
    assert calls == ["atomic-1", "atomic-1"]


def test_later_subscriber_failure_does_not_commit_earlier_subscriber_state(
    make_event,
) -> None:
    rule = TemporalRule(
        rule_id="transfer-delay",
        start_event="ActuatorCommand",
        end_event="ProductTransfer",
        min_delay_seconds=1.0,
        max_delay_seconds=4.0,
        topology_from="ActuatorCommand",
        topology_to="ProductTransfer",
    )
    timing = TimingMonitor([rule])
    mosaic = FusionMosaic()
    failure_enabled = True

    def later_subscriber(_event):
        if failure_enabled:
            raise RuntimeError("later subscriber failure")
        return ()

    mosaic.register(
        Subscription(
            name="timing-monitor",
            event_types=timing.event_types,
            handler=timing.handle,
            checkpoint=timing.snapshot_state,
            restore=timing.restore_state,
        )
    )
    mosaic.register(
        Subscription(
            name="later-subscriber",
            event_types=frozenset({"*"}),
            handler=later_subscriber,
        )
    )

    start = make_event(
        event_id="atomic-2-start",
        event_type="ActuatorCommand",
        seconds=0,
    )
    with pytest.raises(RuntimeError, match="later subscriber failure"):
        mosaic.publish(start)

    failure_enabled = False
    end = make_event(
        event_id="atomic-2-end",
        event_type="ProductTransfer",
        seconds=2,
    )
    receipt = mosaic.publish(end)
    findings = tuple(
        output.value
        for output in receipt.outputs
        if isinstance(output.value, TimingFinding)
    )

    assert findings == ()
