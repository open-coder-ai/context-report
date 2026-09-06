"""`context-report produce|verify`: statements of fact about artifacts, never verdicts on them."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

from context_report.efficacy.cli import add_efficacy_parser, run_efficacy
from context_report.produce.run import add_produce_parser, run_produce
from context_report.run.cli import add_run_parser, run_run
from context_report.run.judge_cli import (
    add_compare_parser,
    add_judge_parser,
    run_compare,
    run_judge,
)
from context_report.verify import Verification, verify_statement


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="context-report")
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_produce_parser(subparsers)
    add_efficacy_parser(subparsers)
    add_run_parser(subparsers)
    add_judge_parser(subparsers)
    add_compare_parser(subparsers)

    verify_parser = subparsers.add_parser(
        "verify",
        help="check a statement is well-formed and, optionally, bound to a subject artifact",
    )
    verify_parser.add_argument("statement", help="path to the statement JSON file")
    verify_parser.add_argument(
        "--subject", default=None, help="path to the subject artifact (file or directory)"
    )
    verify_parser.add_argument(
        "--json", action="store_true", dest="as_json", help="print the Verification as JSON"
    )
    return parser


def _human_report(verification: Verification) -> str:
    lines = []
    for row in verification.rows:
        marker = " (author-reported)" if row.basis == "claimed" else ""
        lines.append(f"{row.attribute}  {row.basis}  {row.result}{marker}")
    lines.append("")
    lines.append(
        f"{len(verification.rows)} row(s): {len(verification.rederivable)} re-derivable, "
        f"{len(verification.claimed)} claimed (author-reported), "
        f"{len(verification.unmeasured)} unmeasured"
    )
    if verification.schema_errors:
        lines.append(f"schema errors ({len(verification.schema_errors)}):")
        lines.extend(f"  - {e}" for e in verification.schema_errors)
    if verification.subject_digest_matches is False:
        lines.append("subject digest MISMATCH: this report does not describe the given artifact")
    # Deliberately "well-formed and bound", never "good" or "passed" -- see Verification.ok.
    lines.append(f"well-formed and bound: {verification.ok}")
    return "\n".join(lines)


def _load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns an exit code; never raises SystemExit itself."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    dispatch = {
        "produce": run_produce,
        "efficacy": run_efficacy,
        "run": run_run,
        "judge": run_judge,
        "compare": run_compare,
    }
    if args.command in dispatch:
        return dispatch[args.command](args)
    if args.command != "verify":
        return 2
    return _run_verify(args)


def _run_verify(args: argparse.Namespace) -> int:
    try:
        stmt = _load_json(args.statement)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: could not read {args.statement}: {exc}", file=sys.stderr)  # noqa: T201
        return 2

    try:
        verification = verify_statement(stmt, subject_path=args.subject)
    except (OSError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)  # noqa: T201
        return 2

    if args.as_json:
        print(json.dumps(dataclasses.asdict(verification), indent=2))  # noqa: T201
    else:
        print(_human_report(verification))  # noqa: T201

    if verification.schema_errors or verification.subject_digest_matches is False:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
