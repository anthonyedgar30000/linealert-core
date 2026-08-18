from datetime import UTC, datetime

from linealert_core.opcua_adapter import (
    NodeMapping,
    ProxySignal,
    conveyor_arrival_ms,
    qualify_value,
)


class Status:
    def __init__(self, quality: str) -> None:
        self.quality = quality

    def is_good(self) -> bool:
        return self.quality == "good"

    def is_bad(self) -> bool:
        return self.quality == "bad"

    def __str__(self) -> str:
        return self.quality


class Variant:
    def __init__(self, value: object) -> None:
        self.Value = value


class DataValue:
    def __init__(self, value: object, quality: str = "good", timestamp=True) -> None:
        self.Value = Variant(value)
        self.StatusCode = Status(quality)
        self.SourceTimestamp = datetime(2026, 8, 18, tzinfo=UTC) if timestamp else None


MAPPING = NodeMapping("node", ProxySignal.RAW_TIMING_PROXY, "simulator-unit")


def test_good_value_is_transformed_and_evidence_preserved() -> None:
    result = qualify_value(MAPPING, DataValue(120))
    assert result.value == 120
    assert result.quality == "good"
    assert result.status_code == "good"
    assert result.reason_code == "EVIDENCE.OPCUA_STATUS_GOOD"


def test_bad_status_never_releases_value() -> None:
    result = qualify_value(MAPPING, DataValue(120, quality="bad"))
    assert result.value is None
    assert result.quality == "bad"


def test_missing_source_timestamp_fails_closed() -> None:
    result = qualify_value(MAPPING, DataValue(120, timestamp=False))
    assert result.value is None
    assert result.quality == "unknown"
    assert result.reason_code == "EVIDENCE.SOURCE_TIMESTAMP_MISSING"


def test_conveyor_arrival_is_inside_declared_center_model() -> None:
    assert 2490 < conveyor_arrival_ms(120) < 2505
