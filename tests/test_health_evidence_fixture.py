import json
from pathlib import Path

from linealert_core import (
    build_core_from_config,
    condition_signal_projection_to_dict,
    load_condition_signal_bindings,
    load_events,
    project_replay_condition_signals,
    replay_events,
)


ROOT = Path(__file__).resolve().parents[1]


def test_health_core_evidence_fixture_matches_deterministic_replay() -> None:
    core = build_core_from_config(ROOT / "examples" / "labeler_demo_config.json")
    events = load_events(ROOT / "examples" / "labeler_demo_events.jsonl")
    summary = replay_events(core, events)
    bindings = load_condition_signal_bindings(
        ROOT / "examples" / "condition_signal_bindings.json"
    )
    rendered = condition_signal_projection_to_dict(
        project_replay_condition_signals(summary, bindings)
    )

    fixture_path = ROOT / "ui" / "app" / "health" / "core-condition-evidence.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert rendered == fixture
