"""Command-line entry point for deterministic LineAlert event replay."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one deterministic replay and emit a JSON report."""

    args = build_parser().parse_args(argv)

    try:
        core = build_core_from_config(args.config)
        events = load_events(args.input, input_format=args.format)
        report = summary_to_dict(replay_events(core, events))
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
