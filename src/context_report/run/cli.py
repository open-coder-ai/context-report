"""`context-report run MANIFEST`: deterministic rows, then recorded arms per subject and model."""

from __future__ import annotations

import argparse
from typing import Any


def add_run_parser(subparsers: Any) -> None:
    p = subparsers.add_parser("run", help="run every producer from a manifest (see spec/run/v0.1)")
    p.add_argument("manifest", help="path to run.json")


def run_run(args: argparse.Namespace) -> int:
    raise NotImplementedError(
        "`context-report run` is being built; see plan/context-attestation.md"
    )
