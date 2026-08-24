import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from linealert_core.condition_projection import (
    ConditionProjectionError,
    TimingConditionBinding,
    condition_signal_projection_to_dict,
    load_condition_signal_bindings,
    project_replay_condition_signals,
    project_timing_finding,
)
from linealert_core.events import EventQuality
from linealert_core.timing import TimingFinding, TimingStatus


class ConditionProjectionTests(unittest.TestCase):
    def finding(
        self,
        *,
        rule_id: str = "label-presentation-delay",
        delay_ms: float = 155.0,
        start_quality: EventQuality = EventQuality.GOOD,
        end_quality: EventQuality = EventQuality.GOOD,
    ) -> TimingFinding:
        start = datetime(2026, 8, 24, 7, 0, 0, tzinfo=UTC)
        end = start + timedelta(milliseconds=delay_ms)
        return TimingFinding(
            rule_id=rule_id,
            asset_id="LABELER-DEMO-01",
            correlation_id="cycle-42",
            start_timestamp=start,
            end_timestamp=end,
            delay_seconds=delay_ms / 1000.0,
            min_delay_seconds=0.05,
            max_delay_seconds=0.35,
            status=TimingStatus.WITHIN,
            topology_from="LabelFeedCommand",
            topology_to="LabelAtPeelPoint",
            start_event_id="evt-feed-command",
            end_event_id="evt-label-at-peel",
            start_source_id="plc-labeler-01",
            end_source_id="plc-labeler-01",
            start_quality=start_quality,
            end_quality=end_quality,
        )

    def binding(self) -> TimingConditionBinding:
        return TimingConditionBinding(
            signal_name="label_presentation_delay_ms",
            rule_id="label-presentation-delay",
            semantic="measured_label_feed_to_peel_point_delay",
            scope="replay_measurement_candidate",
            unit="ms",
        )

    def test_projects_exact_measured_delay_without_diagnostic_upgrade(self) -> None:
        observation = project_timing_finding(self.finding(), self.binding())

        self.assertEqual(observation.signal_name, "label_presentation_delay_ms")
        self.assertAlmostEqual(observation.value, 155.0)
        self.assertEqual(observation.unit, "ms")
        self.assertEqual(observation.min_value, 50.0)
        self.assertEqual(observation.max_value, 350.0)
        self.assertEqual(observation.relationship_id, "relationship:label-presentation-delay")
        self.assertEqual(observation.temporal_rule_status, "within")
        self.assertEqual(observation.quality, "good")
        self.assertEqual(observation.start_event_id, "evt-feed-command")
        self.assertEqual(observation.end_event_id, "evt-label-at-peel")
        self.assertEqual(
            observation.source_timestamp,
            "2026-08-24T07:00:00.155000+00:00",
        )

    def test_non_good_input_quality_is_preserved_not_upgraded(self) -> None:
        observation = project_timing_finding(
            self.finding(end_quality=EventQuality.SUSPECT),
            self.binding(),
        )

        self.assertEqual(observation.quality, "suspect")
        self.assertEqual(
            observation.reason_code,
            "EVIDENCE.RELATIONSHIP_INPUT_SUSPECT",
        )

    def test_rule_mismatch_is_refused(self) -> None:
        finding = self.finding(rule_id="other-rule")

        with self.assertRaisesRegex(ConditionProjectionError, "cannot project"):
            project_timing_finding(finding, self.binding())

    def test_projection_selects_only_explicitly_bound_rules(self) -> None:
        configured = self.finding()
        unrelated = self.finding(rule_id="inspection-delay", delay_ms=90.0)
        summary = SimpleNamespace(
            results=(SimpleNamespace(timing_findings=(configured, unrelated)),)
        )

        projection = project_replay_condition_signals(summary, (self.binding(),))
        rendered = condition_signal_projection_to_dict(projection)

        self.assertEqual(rendered["count"], 1)
        self.assertEqual(
            rendered["observations"][0]["reason_code"],
            "EVIDENCE.RELATIONSHIP_DELAY_MEASURED",
        )
        self.assertEqual(
            rendered["observations"][0]["provenance"],
            "correlated_machine_event_source_timestamps",
        )
        self.assertEqual(
            rendered["observations"][0]["start_source_id"],
            "plc-labeler-01",
        )
        self.assertIn("does not establish physical root cause", rendered["claim_boundary"])

    def test_binding_loader_rejects_duplicate_rule_mapping(self) -> None:
        document = {
            "schema_version": "linealert.condition-signal-bindings.v1",
            "bindings": [
                {
                    "signal_name": "signal_a_ms",
                    "rule_id": "same-rule",
                    "semantic": "semantic_a",
                    "scope": "replay_measurement_candidate",
                    "unit": "ms",
                },
                {
                    "signal_name": "signal_b_ms",
                    "rule_id": "same-rule",
                    "semantic": "semantic_b",
                    "scope": "replay_measurement_candidate",
                    "unit": "ms",
                },
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bindings.json"
            path.write_text(json.dumps(document), encoding="utf-8")

            with self.assertRaisesRegex(ConditionProjectionError, "rule IDs must be unique"):
                load_condition_signal_bindings(path)

    def test_health_fixture_matches_deterministic_labeler_replay(self) -> None:
        from linealert_core.replay import build_core_from_config, load_events, replay_events

        root = Path(__file__).resolve().parents[1]
        core = build_core_from_config(root / "examples" / "labeler_demo_config.json")
        events = load_events(root / "examples" / "labeler_demo_events.jsonl")
        summary = replay_events(core, events)
        bindings = load_condition_signal_bindings(
            root / "examples" / "condition_signal_bindings.json"
        )
        rendered = condition_signal_projection_to_dict(
            project_replay_condition_signals(summary, bindings)
        )

        fixture_path = root / "ui" / "app" / "health" / "core-condition-evidence.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.assertEqual(rendered, fixture)


if __name__ == "__main__":
    unittest.main()
