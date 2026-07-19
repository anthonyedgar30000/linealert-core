from __future__ import annotations

import pytest

from linealert_core import (
    EventIdentityCollision,
    FusionMosaic,
    Subscription,
)


def test_mosaic_delivers_only_to_declared_consumers(make_event) -> None:
    delivered: list[str] = []
    mosaic = FusionMosaic()
    mosaic.register(
        Subscription(
            name="timing",
            event_types=frozenset({"ActuatorCommand"}),
            handler=lambda event: delivered.append(event.event_type) or (),
        )
    )
    mosaic.register(
        Subscription(
            name="unrelated",
            event_types=frozenset({"OperatorLogin"}),
            handler=lambda event: delivered.append("wrong") or (),
        )
    )

    receipt = mosaic.publish(
        make_event(event_id="e-1", event_type="ActuatorCommand")
    )

    assert receipt.delivered_to == ("timing",)
    assert delivered == ["ActuatorCommand"]


def test_exact_duplicate_is_idempotent(make_event) -> None:
    mosaic = FusionMosaic()
    calls: list[str] = []
    mosaic.register(
        Subscription(
            name="recorder",
            event_types=frozenset({"*"}),
            handler=lambda event: calls.append(event.event_id) or (),
        )
    )
    event = make_event(event_id="e-1", event_type="ActuatorCommand")

    first = mosaic.publish(event)
    duplicate = mosaic.publish(event)

    assert first.duplicate is False
    assert duplicate.duplicate is True
    assert calls == ["e-1"]


def test_divergent_content_under_same_identity_is_rejected(make_event) -> None:
    mosaic = FusionMosaic()
    mosaic.publish(make_event(event_id="e-1", event_type="ActuatorCommand"))

    with pytest.raises(EventIdentityCollision):
        mosaic.publish(make_event(event_id="e-1", event_type="ProductTransfer"))
