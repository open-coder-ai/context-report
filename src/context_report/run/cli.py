"""`context-report run MANIFEST`: deterministic rows, then recorded arms per subject and model."""

from __future__ import annotations

import argparse
import dataclasses
import sys
from typing import Any

from context_report.run.manifest import ManifestError, load
from context_report.run.runner import RunError, dry_run_report, preflight, run


def add_run_parser(subparsers: Any) -> None:
    p = subparsers.add_parser("run", help="run every producer from a manifest (see spec/run/v0.1)")
    p.add_argument("manifest", help="path to run.json")
    p.add_argument(
        "--dry-run", action="store_true", help="print the call budget only; touch no model"
    )
    p.add_argument("--n", type=int, default=None, help="override arms.nPerArm (for smoke runs)")


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
        run(manifest)
    except (ManifestError, RunError) as exc:
        print(f"error: {exc}", file=sys.stderr)  # noqa: T201
        return 2
    return 0
