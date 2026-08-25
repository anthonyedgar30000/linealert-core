"""Command-line entry point for the LineAlert causal packaging emulator."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from .causal_emulator import EmulatorConfig, LaneBDegradationEmulator
from .drift_analysis import GradualDriftAnalyzer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a seeded gradual Lane B drift experiment")
    parser.add_argument("--cycles", type=int, default=120)
    parser.add_argument("--seed", type=int, default=20260825)
    parser.add_argument("--drift-onset", type=int, default=20)
    parser.add_argument("--intervention-cycle", type=int)
    parser.add_argument("--visible-output", type=Path, required=True)
    parser.add_argument("--events-output", type=Path)
    parser.add_argument("--ground-truth-output", type=Path)
    parser.add_argument("--analysis-output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = EmulatorConfig(
        cycles=args.cycles,
        seed=args.seed,
        drift_onset_cycle=args.drift_onset,
        intervention_cycle=args.intervention_cycle,
    )
    run = LaneBDegradationEmulator(config).run()
    assessment = GradualDriftAnalyzer().analyze(run)
    manifest = {
        "emulator": "lane-b-gradual-drift-v1",
        "config": {**asdict(config), "start_time": config.start_time.isoformat()},
        "evidence_fingerprint_sha256": run.evidence_fingerprint,
        "records": run.visible_records(),
    }
    args.visible_output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if args.events_output is not None:
        events_jsonl = "\n".join(
            json.dumps(event, sort_keys=True) for event in run.machine_event_records()
        )
        args.events_output.write_text(events_jsonl + "\n", encoding="utf-8")
    if args.ground_truth_output is not None:
        truth = {
            "warning": "SIMULATOR-PRIVATE GROUND TRUTH - DO NOT PRESENT AS OBSERVED EVIDENCE",
            "records": run.ground_truth_records(),
        }
        args.ground_truth_output.write_text(json.dumps(truth, indent=2), encoding="utf-8")
    if args.analysis_output is not None:
        args.analysis_output.write_text(
            json.dumps(assessment.to_dict(), indent=2), encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "cycles": config.cycles,
                "visible_output": str(args.visible_output),
                "ground_truth_output": (
                    str(args.ground_truth_output) if args.ground_truth_output else None
                ),
                "events_output": str(args.events_output) if args.events_output else None,
                "analysis_output": str(args.analysis_output) if args.analysis_output else None,
                "analysis_status": assessment.status,
                "recovery_status": assessment.recovery_status,
                "evidence_fingerprint_sha256": run.evidence_fingerprint,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
