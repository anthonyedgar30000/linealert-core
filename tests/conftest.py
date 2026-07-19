from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from linealert_core import MachineEvent


@pytest.fixture
def base_time() -> datetime:
    return datetime(2026, 7, 19, 12, 0, tzinfo=UTC)


@pytest.fixture
def make_event(base_time: datetime):
    def factory(
        *,
        event_id: str,
        event_type: str,
        correlation_id: str = "cycle-1",
        seconds: float = 0,
        component_id: str = "labeler",
    ) -> MachineEvent:
        return MachineEvent(
            event_id=event_id,
            source_id="plc-1",
            asset_id="LABELER-04",
            component_id=component_id,
            event_type=event_type,
            timestamp=base_time + timedelta(seconds=seconds),
            correlation_id=correlation_id,
        )

    return factory
