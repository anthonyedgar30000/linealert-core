from pathlib import Path


def test_live_condition_demo_example_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    example = root / "examples" / "live_condition_demo.py"
    assert example.exists()
    text = example.read_text(encoding="utf-8")
    assert "LiveConditionConsumer" in text
    assert "live_condition_summary_to_dict" in text
