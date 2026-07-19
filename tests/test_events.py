from __future__ import annotations

from datetime import datetime

import pytest

from linealert_core import MachineEvent


def test_event_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        MachineEvent(
            event_id="e-1",
            source_id="plc-1",
            asset_id="LABELER-04",
            component_id="sensor-1",
            event_type="ProductDetected",
            timestamp=datetime(2026, 7, 19, 12, 0),
            correlation_id="cycle-1",
        )


def test_event_has_stable_canonical_fingerprint(make_event) -> None:
    event = make_event(event_id="e-1", event_type="ProductDetected")
    payload = event.canonical_payload()

    assert payload["asset_id"] == "LABELER-04"
    assert len(event.fingerprint) == 64
