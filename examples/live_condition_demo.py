"""Run the labeler demo events through the live condition projection path."""

from pathlib import Path

from linealert_core import (
    DeterministicStreamSimulator,
    LiveConditionConsumer,
    build_core_from_config,
    live_condition_summary_to_dict,
    load_condition_signal_bindings,
    load_events,
)

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    events = load_events(ROOT / "examples" / "labeler_demo_events.jsonl")
    bindings = load_condition_signal_bindings(
        ROOT / "examples" / "condition_signal_bindings.json"
    )
    consumer = LiveConditionConsumer(
        build_core_from_config(ROOT / "examples" / "labeler_demo_config.json"),
        bindings,
    )
    summary = consumer.consume_all(
        DeterministicStreamSimulator(
            events=events,
            session_id="labeler-live-demo",
            ingestion_delay_seconds=0.05,
            clock_quality="synchronized",
            transport_attributes={"source": "bounded-lab-simulator"},
        )
    )
    report = live_condition_summary_to_dict(summary)
    for observation in report["condition_signals"]["observations"]:
        print(
            f"{observation['signal']}: {observation['value']} {observation['unit']} "
            f"({observation['temporal_rule_status']})"
        )


if __name__ == "__main__":
    main()
