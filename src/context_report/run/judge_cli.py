"""`context-report judge OUT --judge MODEL` and `context-report compare OUT`: after the arms ran."""

from __future__ import annotations

import argparse
from typing import Any


def add_judge_parser(subparsers: Any) -> None:
    p = subparsers.add_parser("judge", help="grade recorded transcripts with a judge model")
    p.add_argument("out", help="the run's output directory")
    p.add_argument("--judge", required=True, help="provider/id of the judge model")


def add_compare_parser(subparsers: Any) -> None:
    p = subparsers.add_parser("compare", help="table of efficacy across models or subjects")
    p.add_argument("out", help="the run's output directory")


def run_judge(args: argparse.Namespace) -> int:
    raise NotImplementedError("`context-report judge` is being built")


def run_compare(args: argparse.Namespace) -> int:
    raise NotImplementedError("`context-report compare` is being built")
