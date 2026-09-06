"""`context-report produce`: run every v0.1 producer against one artifact for one target agent."""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import hashlib
import json
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from context_report import __version__
from context_report.produce import payloads
from context_report.produce.cost import context_tokens_row, injected_text_paths, latency_rows
from context_report.produce.fault import client_dependent_rows, malformed_output_row
from context_report.produce.reachability import reachability_row
from context_report.rows import (
    ATTRIBUTES,
    CLAIMED,
    NOT_APPLICABLE,
    NOT_AVAILABLE,
    Row,
    not_applicable_for,
    not_measured,
)
from context_report.statement import (
    SUBJECT_KINDS,
    Producer,
    Target,
    digest_path,
    now_utc,
    statement,
    validate,
)

DEFAULT_PRODUCER_ID = "https://github.com/open-coder-ai/context-report#local"
EXECUTABLE_KINDS = frozenset({"plugin", "hook", "mcp-server"})
EXEC_ATTRIBUTES = (
    "reachability",
    "fault.malformedOutput",
    "cost.latency_ms",
    "fault.scriptMissing",
    "fault.interpreterMissing",
    "fault.timeout",
)
_ORDER = {name: i for i, name in enumerate(ATTRIBUTES)}


@contextlib.contextmanager
def _scoped_environ(env: dict[str, str]) -> Iterator[None]:
    """Set variables for the producers' subprocesses, then restore -- never leak between runs."""
    saved = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _with_environment(row: Row, env: dict[str, str]) -> Row:
    """Record the variables the command was run under; a hook's reachability depends on them."""
    if not env:
        return row
    return dataclasses.replace(row, environment={**(row.environment or {}), "env": dict(env)})


def _with_payload(row: Row, provenance: dict[str, Any]) -> Row:
    """Record which payload shape probed the hook; a generic shape may have hit an early exit."""
    return dataclasses.replace(row, conditions={**(row.conditions or {}), "payload": provenance})


def _unmeasured_exec_rows(subject_kind: str, binding: tuple[object, ...]) -> list[Row]:
    why = (
        f"subjectKind {subject_kind} has nothing to execute"
        if subject_kind not in EXECUTABLE_KINDS
        else "no hook command was declared for this artifact"
    )
    return [
        not_measured(attr, NOT_APPLICABLE, why, inputs=(subject_kind,), binding=binding)
        for attr in EXEC_ATTRIBUTES
    ]


def _apply_applicability(
    rows: list[Row], subject_kind: str, binding: tuple[object, ...]
) -> list[Row]:
    """A (kind, attribute) pair the spec lists as not applicable is a NotApplicable row, always."""
    excluded = not_applicable_for(subject_kind)
    out = []
    for row in rows:
        if row.attribute not in excluded or row.result == NOT_APPLICABLE:
            out.append(row)
            continue
        out.append(
            not_measured(
                row.attribute,
                NOT_APPLICABLE,
                f"{row.attribute} does not apply to subjectKind {subject_kind} in v0.1",
                basis=row.basis,
                inputs=(subject_kind,),
                binding=binding,
            )
        )
    return out


def produce_statement(  # noqa: PLR0913 -- keyword-only; these are the CLI's flags
    *,
    subject: Path,
    subject_kind: str,
    target: str,
    hook_command: str | None = None,
    env: dict[str, str] | None = None,
    producer_id: str = DEFAULT_PRODUCER_ID,
    n: int = 50,
    client_version: str | None = None,
    efficacy_row: Row | None = None,
    byproducts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Every v0.1 attribute gets a row. What v0.1 cannot measure says so; nothing is silent.

    `efficacy_row` is the measured row from the efficacy engine when a run produced one; without
    it the row is the honest NotAvailable. `byproducts` lists what the run recorded (transcripts).
    """
    if subject_kind not in SUBJECT_KINDS:
        raise ValueError(f"subjectKind must be one of {SUBJECT_KINDS}, not {subject_kind!r}")
    env = dict(env or {})
    started = now_utc()
    digest_before = digest_path(subject)  # the artifact as the user has it, before anything runs
    # Every inputHash starts with these three, so a row is bound to this subject and this target.
    binding: tuple[object, ...] = (digest_before, target, client_version)
    rows: list[Row] = []
    if hook_command:
        payload, provenance = payloads.pre_tool_payload(target, "true", cwd=str(subject))
        with _scoped_environ(env):  # subprocesses inherit this; it is recorded on each row
            rows.append(
                _with_environment(
                    _with_payload(
                        reachability_row(hook_command, subject, payload=payload, binding=binding),
                        provenance,
                    ),
                    env,
                )
            )
            rows.append(
                _with_environment(
                    _with_payload(
                        malformed_output_row(
                            hook_command,
                            subject,
                            target=target,
                            control_payload=payload,
                            binding=binding,
                        ),
                        provenance,
                    ),
                    env,
                )
            )
            rows.append(
                _with_payload(
                    latency_rows(
                        hook_command,
                        payload,
                        n=n,
                        cwd=str(subject),
                        env_note={"env": env} if env else None,
                        binding=binding,
                    ),
                    provenance,
                )
            )
        rows.extend(client_dependent_rows(target, binding=binding))
    else:
        rows.extend(_unmeasured_exec_rows(subject_kind, binding))

    rows.append(context_tokens_row(injected_text_paths(subject, subject_kind), binding=binding))
    inputs = (subject_kind,)
    rows.append(
        not_measured(
            "conformance",
            NOT_AVAILABLE,
            "v0.1 producer does not validate the bundle against the target agent's plugin schema",
            inputs=inputs,
            binding=binding,
        )
    )
    rows.append(
        not_measured(
            "decision",
            NOT_AVAILABLE,
            "no declared positive/negative cases were supplied; v0.1 has no decision replay",
            inputs=inputs,
            binding=binding,
        )
    )
    rows.append(
        not_measured(
            "interference",
            NOT_AVAILABLE,
            "no co-installed artifacts were declared; v0.1 producer does not measure interference",
            inputs=inputs,
            binding=binding,
        )
    )
    if efficacy_row is not None:
        if efficacy_row.attribute != "efficacy":
            raise ValueError(f"efficacy_row must be an efficacy row, not {efficacy_row.attribute}")
        rows.append(efficacy_row)
    else:
        rows.append(
            not_measured(
                "efficacy",
                NOT_AVAILABLE,
                "efficacy (paired ablation) was not run; use `context-report run` with models",
                basis=CLAIMED,
            )
        )
    rows = _apply_applicability(rows, subject_kind, binding)
    rows.sort(key=lambda r: _ORDER.get(r.attribute, len(_ORDER)))

    if (
        digest_path(subject) != digest_before
    ):  # a producer bug: measuring must not alter the subject
        raise ValueError(
            "a producer changed the subject while measuring it; refusing to bind a statement to "
            "an artifact that no longer matches what the user has"
        )

    args_blob = json.dumps(
        {
            "subjectKind": subject_kind,
            "target": target,
            "hookCommand": hook_command,
            "env": env,
            "n": n,
            "clientVersion": client_version,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    configuration = [
        {
            "name": "produce-args",
            "digest": {"sha256": hashlib.sha256(args_blob.encode("utf-8")).hexdigest()},
            "mediaType": "application/json",
        }
    ]
    stmt = statement(
        subject_name=subject.name,
        subject_sha256=digest_before,
        subject_kind=subject_kind,
        target=Target(target, client_version),
        producer=Producer(producer_id, {"context-report": __version__}),
        rows=rows,
        started_on=started,
        finished_on=now_utc(),
        configuration=configuration,
        byproducts=byproducts,
    )
    errors = validate(stmt)
    if errors:  # a producer bug, never a user error -- surface loudly
        raise ValueError("produced statement failed its own schema: " + "; ".join(errors))
    return stmt


def _check_out_location(out: str | None, subject: Path) -> None:
    """Writing the report into the artifact would change the digest the report is bound to."""
    if out and Path(out).resolve().is_relative_to(subject.resolve()):
        raise ValueError("--out must not be inside --subject: it would change the artifact digest")


def _parse_env(pairs: list[str]) -> dict[str, str]:
    env: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"--env expects VAR=VALUE, got {pair!r}")
        key, value = pair.split("=", 1)
        env[key] = value
    return env


def add_produce_parser(subparsers: Any) -> None:
    p = subparsers.add_parser(
        "produce", help="run every v0.1 producer against one artifact for one target agent"
    )
    p.add_argument("--subject", required=True, help="artifact path (file or directory)")
    p.add_argument("--kind", required=True, choices=SUBJECT_KINDS, dest="subject_kind")
    p.add_argument("--target", required=True, help="agent id, e.g. claude_code, copilot, cursor")
    p.add_argument("--hook-command", default=None, help="the hook command exactly as registered")
    p.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="VAR=VALUE",
        help="environment the command runs under (e.g. CLAUDE_PLUGIN_ROOT=…); recorded per row",
    )
    p.add_argument("--producer-id", default=DEFAULT_PRODUCER_ID)
    p.add_argument("--client-version", default=None)
    p.add_argument("--n", type=int, default=50, help="latency samples")
    p.add_argument("--out", default=None, help="write the statement here instead of stdout")


def run_produce(args: argparse.Namespace) -> int:
    try:
        env = _parse_env(args.env)
        subject = Path(args.subject)
        if not subject.exists():
            raise FileNotFoundError(args.subject)
        _check_out_location(args.out, subject)
        stmt = produce_statement(
            subject=subject,
            subject_kind=args.subject_kind,
            target=args.target,
            hook_command=args.hook_command,
            env=env,
            producer_id=args.producer_id,
            n=args.n,
            client_version=args.client_version,
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
