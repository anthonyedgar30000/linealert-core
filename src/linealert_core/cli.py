"""Command-line entry point for deterministic LineAlert event replay."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .baseline import BaselineComparisonPolicy
from .baseline_io import load_baseline_registry
from .baseline_replay import (
    assess_replay_timing_baselines,
    load_timing_baseline_contexts,
    timing_baseline_assessment_to_dict,
)
from .replay import (
    ReplayInputError,
    build_core_from_config,
    load_events,
    replay_events,
    summary_to_dict,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the replay command-line parser."""

    parser = argparse.ArgumentParser(
        prog="linealert-replay",
        description="Replay JSONL or CSV machine events through LineAlert Core.",
    )
    parser.add_argument("--config", required=True, type=Path, help="JSON rule/topology config")
    parser.add_argument("--input", required=True, type=Path, help="JSONL or CSV event file")
    parser.add_argument(
        "--format",
        choices=("auto", "jsonl", "csv"),
        default="auto",
        help="input format; inferred from the file extension by default",
    )
    parser.add_argument("--output", type=Path, help="write the JSON report to this file")
    parser.add_argument(
        "--baseline-registry",
        type=Path,
        help="optional governed commissioned-baseline registry",
    )
    parser.add_argument(
        "--timing-baseline-contexts",
        type=Path,
        help="explicit timing-rule applicability contexts; requires --baseline-registry",
    )
    parser.add_argument(
        "--baseline-sigma-threshold",
        type=float,
        default=3.0,
        help="sigma multiplier used for baseline drift classification",
    )
    parser.add_argument(
        "--baseline-minimum-absolute-drift",
        type=float,
        default=0.0,
        help="minimum absolute timing drift in seconds",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one deterministic replay and emit a JSON report."""

    args = build_parser().parse_args(argv)

    try:
        if (args.baseline_registry is None) != (
            args.timing_baseline_contexts is None
        ):
            raise ReplayInputError(
                "--baseline-registry and --timing-baseline-contexts "
                "must be supplied together"
            )

        core = build_core_from_config(args.config)
        events = load_events(args.input, input_format=args.format)
        summary = replay_events(core, events)
        report = summary_to_dict(summary)

        if args.baseline_registry is not None:
            registry = load_baseline_registry(args.baseline_registry)
            contexts = load_timing_baseline_contexts(
                args.timing_baseline_contexts
            )
            policy = BaselineComparisonPolicy(
                sigma_threshold=args.baseline_sigma_threshold,
                minimum_absolute_drift=(
                    args.baseline_minimum_absolute_drift
                ),
            )
            assessment = assess_replay_timing_baselines(
                summary,
                registry,
                contexts,
                policy,
            )
            report["timing_baseline_assessment"] = (
                timing_baseline_assessment_to_dict(assessment)
            )
    except (OSError, ReplayInputError, ValueError) as exc:
        print(f"linealert-replay: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(rendered)
    else:
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
