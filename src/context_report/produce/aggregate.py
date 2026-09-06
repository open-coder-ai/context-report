"""Aggregate the three per-hook producers over a plugin's several pre-tool hooks into one row."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from context_report.produce.cost import latency_rows
from context_report.produce.discover import Hook
from context_report.produce.fault import (
    MALFORMED_OUTPUT_ATTRIBUTE,
    MALFORMED_OUTPUT_REASONING,
    malformed_cases,
    malformed_output_row,
)
from context_report.produce.reachability import ATTRIBUTE as REACHABILITY_ATTRIBUTE
from context_report.produce.reachability import CWD_LABELS, reachability_row
from context_report.rows import (
    ERROR,
    FAILED,
    PASSED,
    PERCENTILES,
    RE_DERIVABLE,
    Measurement,
    Row,
    input_hash,
    not_measured,
)

#: Why a discovered hook is measured in v0.1's tally at all, or left out of it.
SKIPPED_REASON = "v0.1 measures pre-tool hooks only"


def _hooks_condition(hooks: list[Hook]) -> list[dict[str, str]]:
    """`conditions.hooks`: the hook ids and commands an aggregate row was computed over."""
    return [{"hook_id": h.hook_id, "command": h.command} for h in hooks]


def _skipped_hooks(skipped: list[Hook]) -> list[dict[str, str]]:
    return [
        {"hook_id": h.hook_id, "event": h.event, "command": h.command, "reason": SKIPPED_REASON}
        for h in skipped
    ]


def aggregate_reachability(
    hooks: list[Hook],
    subject: Path,
    *,
    payload: dict[str, Any],
    skipped: list[Hook] = (),
    binding: tuple[object, ...] = (),
) -> Row:
    """reachability across every measured hook: FAILED if any hook is unreachable from any cwd.

    A hook whose own reachability_row errors (a subprocess exception, not a result) makes the
    whole aggregate an honest Error naming that hook -- there is no measured answer to combine.
    """
    hooks_cond = _hooks_condition(hooks)
    per_hook: dict[str, dict[str, Any]] = {}
    errored: list[str] = []
    reachable_sets: list[set[str]] = []
    unreachable_union: set[str] = set()
    for h in hooks:
        row = reachability_row(h.command, subject, payload=payload, binding=binding)
        if row.result == ERROR:
            errored.append(h.hook_id)
            continue
        per_hook[h.hook_id] = dict(row.values)
        reachable_sets.append(set(row.values["reachable_from"]))
        unreachable_union |= set(row.values["unreachable_from"])
    if errored:
        return not_measured(
            REACHABILITY_ATTRIBUTE,
            ERROR,
            f"reachability could not be measured for hook(s): {', '.join(errored)}",
            inputs=(hooks_cond, payload, list(CWD_LABELS)),
            binding=binding,
        )
    intersection = set.intersection(*reachable_sets) if reachable_sets else set()
    values: dict[str, Any] = {
        "perHook": per_hook,
        "reachable_from": [c for c in CWD_LABELS if c in intersection],
        "unreachable_from": [c for c in CWD_LABELS if c in unreachable_union],
    }
    if skipped:
        values["skippedHooks"] = _skipped_hooks(skipped)
    return Row(
        attribute=REACHABILITY_ATTRIBUTE,
        basis=RE_DERIVABLE,
        result=FAILED if unreachable_union else PASSED,
        input_hash=input_hash(
            *binding, REACHABILITY_ATTRIBUTE, hooks_cond, payload, list(CWD_LABELS)
        ),
        conditions={"cwdTested": list(CWD_LABELS), "hooks": hooks_cond},
        values=values,
        evidence=(),
    )


def aggregate_malformed_output(  # noqa: PLR0913 -- keyword-only; the probe's whole configuration
    hooks: list[Hook],
    subject: Path,
    *,
    target: str,
    control_payload: dict[str, Any] | None,
    skipped: list[Hook] = (),
    binding: tuple[object, ...] = (),
) -> Row:
    """fault.malformedOutput across every measured hook: `wouldAllowAny` is the OR over hooks."""
    hooks_cond = _hooks_condition(hooks)
    cases = malformed_cases(control_payload)
    case_values = list(cases.values())
    per_hook: dict[str, dict[str, Any]] = {}
    errored: list[str] = []
    would_allow_any = False
    for h in hooks:
        row = malformed_output_row(
            h.command, subject, target=target, control_payload=control_payload, binding=binding
        )
        if row.result == ERROR:
            errored.append(h.hook_id)
            continue
        per_hook[h.hook_id] = dict(row.values)
        would_allow_any = would_allow_any or any(v["would_allow"] for v in row.values.values())
    if errored:
        return not_measured(
            MALFORMED_OUTPUT_ATTRIBUTE,
            ERROR,
            f"fault.malformedOutput could not be measured for hook(s): {', '.join(errored)}",
            inputs=(hooks_cond, case_values, target),
            binding=binding,
        )
    values: dict[str, Any] = {"perHook": per_hook, "wouldAllowAny": would_allow_any}
    if skipped:
        values["skippedHooks"] = _skipped_hooks(skipped)
    return Row(
        attribute=MALFORMED_OUTPUT_ATTRIBUTE,
        basis=RE_DERIVABLE,
        result=PASSED,
        input_hash=input_hash(
            *binding, MALFORMED_OUTPUT_ATTRIBUTE, hooks_cond, case_values, target
        ),
        conditions={"cwd": "root", "cases": list(cases), "target": target, "hooks": hooks_cond},
        values=values,
        reasoning=MALFORMED_OUTPUT_REASONING,
    )


def aggregate_latency(  # noqa: PLR0913 -- keyword-only; the probe's whole configuration
    hooks: list[Hook],
    payload: dict[str, Any],
    *,
    n: int,
    cwd: str,
    env_note: dict[str, Any] | None,
    skipped: list[Hook] = (),
    binding: tuple[object, ...] = (),
) -> Row:
    """cost.latency_ms across every measured hook: the total is the sum of the per-hook stats.

    `measurement.stddev` is left unset on the total: the spec's sum-across-hooks rule names
    percentiles/min/max/mean only, and combining independent stddevs into one number the same
    way would assert a precision nobody derived.
    """
    hooks_cond = _hooks_condition(hooks)
    per_hook: dict[str, dict[str, Any]] = {}
    errored: list[str] = []
    measurements: list[Measurement] = []
    environment: dict[str, Any] | None = None
    for h in hooks:
        row = latency_rows(h.command, payload, n=n, cwd=cwd, env_note=env_note, binding=binding)
        if row.result == ERROR:
            errored.append(f"{h.hook_id} ({row.reasoning})")
            continue
        assert row.measurement is not None  # PASSED latency rows always carry a measurement
        per_hook[h.hook_id] = row.measurement.to_dict()
        measurements.append(row.measurement)
        environment = row.environment
    if errored:
        return not_measured(
            "cost.latency_ms",
            ERROR,
            f"latency could not be measured for hook(s): {'; '.join(errored)}",
            inputs=(hooks_cond, payload, n),
            binding=binding,
        )
    total = Measurement(
        unit="ms",
        n=n,
        percentiles={str(p): sum(m.percentiles[str(p)] for m in measurements) for p in PERCENTILES},
        min=sum(m.min for m in measurements),
        max=sum(m.max for m in measurements),
        mean=sum(m.mean for m in measurements),
    )
    values: dict[str, Any] = {"perHook": per_hook}
    if skipped:
        values["skippedHooks"] = _skipped_hooks(skipped)
    return Row(
        attribute="cost.latency_ms",
        basis=RE_DERIVABLE,
        result=PASSED,
        input_hash=input_hash(*binding, "cost.latency_ms", hooks_cond, payload, n),
        environment_sensitive=True,
        environment=environment,
        measurement=total,
        conditions={"n": n, "aggregation": "sum-across-hooks", "hooks": hooks_cond},
        values=values,
    )
