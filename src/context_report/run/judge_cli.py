"""`context-report judge OUT --judge MODEL` and `context-report compare OUT`: after the arms ran."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from context_report.run import compare, judge


def add_judge_parser(subparsers: Any) -> None:
    p = subparsers.add_parser("judge", help="grade recorded transcripts with a judge model")
    p.add_argument("out", help="the manifest's `out` directory (or one run directory)")
    p.add_argument("--judge", required=True, help="provider/id of the judge model")
    p.add_argument("--run", default=None, help="run id under out/runs/ (default: the latest)")


def add_compare_parser(subparsers: Any) -> None:
    p = subparsers.add_parser("compare", help="table of efficacy across models or subjects")
    p.add_argument("out", help="the manifest's `out` directory (or one run directory)")
    p.add_argument("--by", choices=(compare.BY_MODEL, compare.BY_SUBJECT), default=compare.BY_MODEL)
    p.add_argument(
        "--judged", action="store_true", help="prefer *.judged.json, falling back where absent"
    )
    p.add_argument("--run", default=None, help="run id under out/runs/ (default: the latest)")
    p.add_argument("--history", action="store_true", help="every run of this manifest side by side")
    p.add_argument(
        "--rules",
        action="store_true",
        help="with --history: per rule, adherence with / without and lift in every run, and what "
        "the newest run changed",
    )


def _outcome_line(outcome: judge.JudgeOutcome) -> str:
    row = outcome.row or {}
    est = row.get("estimate")
    lift = (
        f"lift={est['pointEstimate']:+.3f} CI[{est['confidenceInterval']['lowerBound']:.3f}, "
        f"{est['confidenceInterval']['upperBound']:.3f}]"
        if est
        else "lift=n/a"
    )
    graded = len((row.get("values") or {}).get("perRule") or [])
    ungraded = len((row.get("values") or {}).get("ungraded") or [])
    return (
        f"{outcome.subject_id}  {outcome.model}  judge={row['conditions']['judgeModel']}  "
        f"result={row['result']}  {lift}  graded={graded} ungraded={ungraded}"
    )


def run_judge(args: argparse.Namespace) -> int:
    try:
        outcomes, code = judge.judge_out(Path(args.out), args.judge, run_id=args.run)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for outcome in outcomes:
        if outcome.judged:
            print(_outcome_line(outcome))
        else:
            msg = f"{outcome.subject_id}  {outcome.model}  skipped: {outcome.message}"
            print(msg, file=sys.stderr)
    if not outcomes:
        print("nothing to judge: no recorded statement had a transcripts bundle", file=sys.stderr)
    return code


def run_compare(args: argparse.Namespace) -> int:
    try:
        if args.history:
            print(compare.render_history(Path(args.out), rules=args.rules))
        else:
            print(
                compare.render_table(
                    Path(args.out), by=args.by, judged=args.judged, run_id=args.run
                )
            )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
