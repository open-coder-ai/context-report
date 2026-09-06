"""`context-report ingest-eval`: turn a vendor `claude plugin eval` result into a statement."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from context_report.efficacy.pluginval import efficacy_row_from_vendor, load
from context_report.produce.run import produce_statement
from context_report.statement import SUBJECT_KINDS

RESULT_MEDIA_TYPE = "application/json"
RESULT_BYPRODUCT_NAME = "aggregate-result.json"


def add_ingest_eval_parser(subparsers: Any) -> None:
    p = subparsers.add_parser(
        "ingest-eval",
        help="ingest a `claude plugin eval --ablation with-without` result as an efficacy row",
    )
    p.add_argument("result", help="path to the vendor's aggregate-result.json")
    p.add_argument("--subject", required=True, help="artifact path (file or directory)")
    p.add_argument("--kind", required=True, choices=SUBJECT_KINDS, dest="subject_kind")
    p.add_argument("--target", required=True, help="agent id, e.g. claude_code, copilot, cursor")
    p.add_argument("--model", required=True, help="the subject model the vendor tool ran")
    p.add_argument("--client-version", default=None)
    p.add_argument("--out", default=None, help="write the statement here instead of stdout")


def run_ingest_eval(args: argparse.Namespace) -> int:
    try:
        result_path = Path(args.result)
        if not result_path.exists():
            raise FileNotFoundError(args.result)
        subject = Path(args.subject)
        if not subject.exists():
            raise FileNotFoundError(args.subject)
        vendor_result = load(result_path)
        row = efficacy_row_from_vendor(vendor_result, model=args.model)
        digest = hashlib.sha256(result_path.read_bytes()).hexdigest()
        stmt = produce_statement(
            subject=subject,
            subject_kind=args.subject_kind,
            target=args.target,
            client_version=args.client_version,
            efficacy_row=row,
            byproducts=[
                {
                    "name": RESULT_BYPRODUCT_NAME,
                    "digest": {"sha256": digest},
                    "mediaType": RESULT_MEDIA_TYPE,
                }
            ],
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)  # noqa: T201
        return 2
    text = json.dumps(stmt, indent=2) + "\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0
