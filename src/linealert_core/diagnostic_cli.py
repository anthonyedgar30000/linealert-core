"""Command-line entry point for symptom-first diagnostic projection."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .diagnostic_io import (
    collect_timing_findings,
    load_diagnostic_engine,
    load_operator_report,
    projection_to_dict,
)
from .diagnostic_projection import DiagnosticProjectionError
from .replay import (
    ReplayInputError,
    build_core_from_config,
    load_events,
    replay_events,
    summary_to_dict,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the diagnostic projection command-line parser."""

    parser = argparse.ArgumentParser(
        prog="linealert-diagnose",
        description=(
            "Replay machine events, preserve the operator timeline, and project "
            "governed troubleshooting knowledge onto the supplied findings."
        ),
    )
    parser.add_argument("--config", required=True, type=Path, help="machine replay config")
    parser.add_argument("--input", required=True, type=Path, help="JSONL or CSV event file")
    parser.add_argument("--guide", required=True, type=Path, help="diagnostic guide JSON")
    parser.add_argument(
        "--operator-report",
        required=True,
        type=Path,
        help="operator issue timeline JSON",
    )
    parser.add_argument(
        "--format",
        choices=("auto", "jsonl", "csv"),
        default="auto",
        help="input format; inferred from the file extension by default",
    )
    parser.add_argument("--output", type=Path, help="write the JSON report to this file")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one deterministic replay and diagnostic projection."""

    args = build_parser().parse_args(argv)

    try:
        core = build_core_from_config(args.config)
        events = load_events(args.input, input_format=args.format)
        summary = replay_events(core, events)
        engine = load_diagnostic_engine(
            args.guide,
            machine_profile=core.machine_profile,
            topology=core.topology,
        )
        operator_report = load_operator_report(args.operator_report)
        projection = engine.project(
            operator_report=operator_report,
            timing_findings=collect_timing_findings(summary.results),
        )
        report = summary_to_dict(summary)
        report["diagnostic_projection"] = projection_to_dict(projection)
    except (
        OSError,
        DiagnosticProjectionError,
        ReplayInputError,
        ValueError,
    ) as exc:
        print(f"linealert-diagnose: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
