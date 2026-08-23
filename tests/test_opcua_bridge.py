import asyncio
import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from linealert_core.evidence_hierarchy import load_evidence_hierarchy_profile
from linealert_core.opcua_bridge import (
    JsonlRecorder,
    Snapshot,
    evaluate_proxy_claims,
    replay_jsonl,
)


def qualified_payload(value: float = 120.0) -> dict:
    observed = datetime.now(UTC) - timedelta(milliseconds=25)
    return {
        "schema_version": "linealert.observation.snapshot.v1",
        "connected": True,
        "source_id": "microsoft-opc-plc-local",
        "asset_id": "SIM-OPCPLC-01",
        "reason_code": "EVIDENCE.OPCUA_SAMPLE_QUALIFIED",
        "signals": {
            "rpm": {
                "signal": "rpm",
                "value": value,
                "unit": "rpm",
                "source_timestamp": observed.isoformat(),
                "quality": "good",
                "reason_code": "EVIDENCE.OPCUA_STATUS_GOOD",
                "observation_id": "microsoft-opc-plc-local:1:rpm",
            }
        },
    }


class OpcuaBridgeTests(unittest.TestCase):
    def test_proxy_claims_support_simulator_state_but_refuse_physical_state(self) -> None:
        payload = qualified_payload()
        payload["semantic_admission"] = {
            "signals": {
                "rpm": {
                    "admitted": True,
                    "scope": "simulator_only",
                }
            }
        }
        profile = load_evidence_hierarchy_profile(
            Path(__file__).resolve().parents[1] / "profiles" / "evidence-hierarchy-v1.json"
        )

        claims = evaluate_proxy_claims(payload, profile)["assessments"]

        simulator = claims["simulator.motor_speed_proxy"]
        self.assertEqual(simulator["status"], "SUPPORTED")
        self.assertEqual(simulator["evidence_level"], 1)
        self.assertFalse(simulator["authorized_action"])

        physical = claims["physical.motor_speed"]
        self.assertEqual(physical["status"], "INSUFFICIENT")
        self.assertEqual(physical["evidence_level"], 0)
        self.assertEqual(
            physical["observations"][0]["reason_code"],
            "EVIDENCE.HIERARCHY_SIMULATOR_PHYSICAL_CLAIM_REFUSED",
        )
        self.assertFalse(physical["authorized_action"])

    def test_disconnect_retains_last_sample_only_as_stale_evidence(self) -> None:
        snapshot = Snapshot()
        snapshot.replace(qualified_payload())

        unavailable = snapshot.mark_unavailable(
            reason_code="EVIDENCE.OPCUA_CONNECTION_UNAVAILABLE",
            error="ConnectionError",
        )

        self.assertFalse(unavailable["connected"])
        self.assertEqual(
            unavailable["reason_code"], "EVIDENCE.OPCUA_CONNECTION_UNAVAILABLE"
        )
        self.assertEqual(unavailable["signals"]["rpm"]["quality"], "stale")
        self.assertEqual(
            unavailable["signals"]["rpm"]["reason_code"], "EVIDENCE.TELEMETRY_STALE"
        )
        self.assertEqual(unavailable["signals"]["rpm"]["value"], 120.0)
        self.assertGreaterEqual(unavailable["signals"]["rpm"]["age_ms"], 0)

    def test_jsonl_capture_and_replay_preserve_evidence_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            capture = Path(temp_dir) / "capture.jsonl"
            recorder = JsonlRecorder(capture)
            original = qualified_payload(123.0)
            recorder.append(original)

            written = json.loads(capture.read_text(encoding="utf-8"))
            self.assertEqual(
                written["signals"]["rpm"]["observation_id"],
                "microsoft-opc-plc-local:1:rpm",
            )

            replayed = Snapshot()
            asyncio.run(replay_jsonl(capture, replayed, 0))
            payload = replayed.get()
            self.assertEqual(payload["transport"], "deterministic-replay")
            self.assertEqual(payload["signals"]["rpm"]["value"], 123.0)
            self.assertEqual(
                payload["signals"]["rpm"]["observation_id"],
                "microsoft-opc-plc-local:1:rpm",
            )


if __name__ == "__main__":
    unittest.main()
