"""`context-report run MANIFEST`: deterministic rows, then recorded arms per subject and model."""

from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path
from typing import Any

from context_report.run import layout
from context_report.run.manifest import ManifestError, load
from context_report.run.runner import SUMMARY_FILENAME, RunError, dry_run_report, preflight, run


def add_run_parser(subparsers: Any) -> None:
    p = subparsers.add_parser("run", help="run every producer from a manifest (see spec/run/v0.1)")
    p.add_argument("manifest", help="path to run.json")
    p.add_argument(
        "--dry-run", action="store_true", help="print the call budget only; touch no model"
    )
    p.add_argument("--n", type=int, default=None, help="override arms.nPerArm (for smoke runs)")
    p.add_argument(
        "--resume",
        action="store_true",
        help="continue the latest run under `out` (or the one named by --run-id): keep every "
        "statement and matching transcript already there; call the model only for what is missing",
    )
    p.add_argument(
        "--run-id",
        default=None,
        help="name this run's directory under `out/runs/` (default: a UTC timestamp)",
    )


def run_run(args: argparse.Namespace) -> int:
    try:
        manifest = load(args.manifest)
        if args.n is not None:
            manifest = dataclasses.replace(
                manifest, arms=dataclasses.replace(manifest.arms, n_per_arm=args.n)
            )
        preflight(manifest)  # leave-one-out / unsupported judge provider: reject before any call
        if args.dry_run:
            print(dry_run_report(manifest))  # noqa: T201
            return 0
        run_dir = run(manifest, resume=args.resume, run_id=args.run_id)
    except (ManifestError, RunError) as exc:
        print(f"error: {exc}", file=sys.stderr)  # noqa: T201
        return 2
    print(_report(run_dir, manifest.out))  # noqa: T201
    return 0


def _report(run_dir: Path, out: Path) -> str:
    """What the developer sees when a run ends: this run's table, and where the history is."""
    lines = [f"run {run_dir.name}: {run_dir}", "", (run_dir / SUMMARY_FILENAME).read_text()]
    runs = layout.run_ids(out)
    if len(runs) > 1:
        lines.append(
            f"{len(runs)} runs of this manifest so far: {out / layout.HISTORY_FILENAME} "
            "lays them side by side (`context-report compare OUT --history`)"
        )
    return "\n".join(lines)
