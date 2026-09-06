"""Ingest an Anthropic `claude plugin eval --ablation with-without` `aggregate-result.json`.

context-report does not run this tool in v0.1; it parses the tool's own result and turns it into
the same `efficacy` row shape every other ablation produces, so a plugin author who already ran
the vendor's evaluator gets a context-report statement without re-running anything.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from context_report.efficacy.core import AdherenceReport, Evidence, action_for
from context_report.efficacy.core import compute_verdict as _compute_verdict
from context_report.efficacy.core import verdict_confirmed as _verdict_confirmed
from context_report.efficacy.grade import Graded
from context_report.efficacy.row import (
    ABLATION_CLAUDE_PLUGIN_EVAL,
    JUDGE_VENDOR,
    efficacy_row,
)
from context_report.efficacy.stats import newcombe_diff, wilson
from context_report.rows import Row

# The one schema version this adapter has been checked against. An unpinned version is still
# ingested -- the vendor promises additive-only changes -- but the row's reasoning says so.
SUPPORTED_SCHEMA_VERSIONS = frozenset({"1"})
# The grader `type` values named in the early-access reference. Anything else is tolerated (its
# `passed` field still counts) and listed under `values.vendor.skippedGraderTypes`.
KNOWN_GRADER_TYPES = frozenset(
    {"regex", "tool_used", "tool_order", "file_exists", "llm", "baseline"}
)
RULE_TAG_PREFIX = "rule:"
VENDOR_TOOL = "claude plugin eval"


@dataclass(frozen=True)
class Grader:
    """One grader's verdict on one run. `score` is optional and otherwise unused here."""

    name: str
    type: str
    passed: bool
    score: float | None = None


@dataclass(frozen=True)
class Run:
    """One arm's single execution. `cost` and token counts are optional in the vendor schema."""

    graders: tuple[Grader, ...]
    cost: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    @property
    def passed(self) -> bool:
        """A run passes only when every grader attached to it passed."""
        return all(g.passed for g in self.graders)


@dataclass(frozen=True)
class Case:
    """One eval case: its paired arms, and the tags that map it to a rule id."""

    name: str
    tags: tuple[str, ...]
    with_runs: tuple[Run, ...]
    without_runs: tuple[Run, ...]

    @property
    def rule_id(self) -> str:
        """The `rule:<id>` tag if present; otherwise the pseudo rule id is the case's own name."""
        for tag in self.tags:
            if tag.startswith(RULE_TAG_PREFIX):
                return tag[len(RULE_TAG_PREFIX) :]
        return self.name


@dataclass(frozen=True)
class VendorResult:
    """One parsed and validated `aggregate-result.json`."""

    schema_version: str
    suite: str | None
    cases: tuple[Case, ...]
    schema_version_pinned: bool
    skipped_grader_types: tuple[str, ...]


def _missing(path: Path, field_name: str) -> ValueError:
    return ValueError(f"{path}: missing required field {field_name!r}")


def _grader_from(raw: dict[str, Any], path: Path, where: str) -> Grader:
    for key in ("name", "type", "passed"):
        if key not in raw:
            raise _missing(path, f"{where}.{key}")
    return Grader(
        name=raw["name"], type=raw["type"], passed=bool(raw["passed"]), score=raw.get("score")
    )


def _run_from(raw: dict[str, Any], path: Path, where: str) -> Run:
    if "graders" not in raw:
        raise _missing(path, f"{where}.graders")
    graders = tuple(
        _grader_from(g, path, f"{where}.graders[{i}]") for i, g in enumerate(raw["graders"])
    )
    tokens = raw.get("tokens") or {}
    return Run(
        graders=graders,
        cost=raw.get("cost"),
        input_tokens=tokens.get("input"),
        output_tokens=tokens.get("output"),
    )


def _case_from(raw: dict[str, Any], path: Path, index: int) -> Case:
    where = f"cases[{index}]"
    if "name" not in raw:
        raise _missing(path, f"{where}.name")
    if "arms" not in raw:
        raise _missing(path, f"{where}.arms")
    arms = raw["arms"]
    if "with" not in arms:
        raise _missing(path, f"{where}.arms.with")
    if "without" not in arms:
        raise _missing(path, f"{where}.arms.without")
    with_runs = tuple(
        _run_from(r, path, f"{where}.arms.with[{i}]") for i, r in enumerate(arms["with"])
    )
    without_runs = tuple(
        _run_from(r, path, f"{where}.arms.without[{i}]") for i, r in enumerate(arms["without"])
    )
    return Case(
        name=raw["name"],
        tags=tuple(raw.get("tags", ())),
        with_runs=with_runs,
        without_runs=without_runs,
    )


def load(path: str | Path) -> VendorResult:
    """Parse and validate one `aggregate-result.json`; a missing required field names the path."""
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    if "schemaVersion" not in raw:
        raise _missing(p, "schemaVersion")
    schema_version = str(raw["schemaVersion"])
    if "cases" not in raw:
        raise _missing(p, "cases")
    cases = tuple(_case_from(c, p, i) for i, c in enumerate(raw["cases"]))
    grader_types = {
        g.type for c in cases for r in (*c.with_runs, *c.without_runs) for g in r.graders
    }
    return VendorResult(
        schema_version=schema_version,
        suite=raw.get("suite"),
        cases=cases,
        schema_version_pinned=schema_version in SUPPORTED_SCHEMA_VERSIONS,
        skipped_grader_types=tuple(sorted(grader_types - KNOWN_GRADER_TYPES)),
    )


def _pool_by_rule(cases: tuple[Case, ...]) -> dict[str, list[Case]]:
    pooled: dict[str, list[Case]] = {}
    for c in cases:
        pooled.setdefault(c.rule_id, []).append(c)
    return pooled


def _report_for_rule(rule_id: str, cases: list[Case]) -> tuple[AdherenceReport, str | None]:
    """Pool every case tagged for `rule_id` into one `AdherenceReport`; second item is a caveat."""
    with_counts = [len(c.with_runs) for c in cases]
    without_counts = [len(c.without_runs) for c in cases]
    with_total, without_total = sum(with_counts), sum(without_counts)
    seen_counts = sorted(set(with_counts) | set(without_counts))
    trials = min(seen_counts) if seen_counts else 0

    note = None
    if len(seen_counts) > 1:
        note = f"rule {rule_id!r}: uneven runs {seen_counts}; trials reported as {trials}"

    with_passes = sum(1 for c in cases for r in c.with_runs if r.passed)
    without_passes = sum(1 for c in cases for r in c.without_runs if r.passed)
    adherence_with = with_passes / with_total if with_total else 0.0
    adherence_without = without_passes / without_total if without_total else 0.0
    lift = adherence_with - adherence_without

    with_ci = wilson(with_passes, with_total)
    without_ci = wilson(without_passes, without_total)
    lift_ci = newcombe_diff(with_passes, with_total, without_passes, without_total)
    # The vendor's paired design runs the same count on both arms; when it doesn't, report the
    # smaller side rather than overstating how much evidence backs the estimate.
    observations = min(with_total, without_total)
    if with_total != without_total:
        extra = f"with={with_total} vs without={without_total} runs; observations={observations}"
        note = f"{note}; {extra}" if note else f"rule {rule_id!r}: {extra}"

    verdict = _compute_verdict(adherence_with, adherence_without, lift)
    evidence = Evidence(
        observations=observations,
        trials=trials,
        with_ci=with_ci,
        without_ci=without_ci,
        lift_ci=lift_ci,
    )
    report = AdherenceReport(
        rule_id=rule_id,
        n=len(cases),
        trials=trials,
        adherence_with=adherence_with,
        adherence_without=adherence_without,
        lift=lift,
        verdict=verdict,
        action=action_for(verdict),
        observations=observations,
        with_ci=with_ci,
        without_ci=without_ci,
        lift_ci=lift_ci,
        confirmed=_verdict_confirmed(verdict, evidence),
    )
    return report, note


def _tokens_per_arm(cases: tuple[Case, ...]) -> dict[str, dict[str, int]] | None:
    """Sum `tokens` across every run per arm; `None` when the result recorded none at all."""
    runs = [r for c in cases for r in (*c.with_runs, *c.without_runs)]
    if not any(r.input_tokens is not None or r.output_tokens is not None for r in runs):
        return None
    totals = {
        "with": {"inputTokens": 0, "outputTokens": 0},
        "without": {"inputTokens": 0, "outputTokens": 0},
    }
    for c in cases:
        for arm, arm_runs in (("with", c.with_runs), ("without", c.without_runs)):
            for r in arm_runs:
                totals[arm]["inputTokens"] += r.input_tokens or 0
                totals[arm]["outputTokens"] += r.output_tokens or 0
    return totals


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def efficacy_row_from_vendor(result: VendorResult, *, model: str) -> Row:
    """Build the `efficacy` row directly from one ingested vendor result."""
    pooled = _pool_by_rule(result.cases)
    reports: list[AdherenceReport] = []
    notes: list[str] = []
    for rule_id, cases in pooled.items():
        report, note = _report_for_rule(rule_id, cases)
        reports.append(report)
        if note:
            notes.append(note)
    graded = Graded(reports=tuple(reports), judge=JUDGE_VENDOR)

    trials_seen = {r.trials for r in reports}
    n_per_arm = min(trials_seen) if trials_seen else 0

    if not result.schema_version_pinned:
        notes.append(
            f"schemaVersion {result.schema_version} not in the pinned set "
            f"{sorted(SUPPORTED_SCHEMA_VERSIONS)}"
        )

    vendor = {
        "tool": VENDOR_TOOL,
        "schemaVersion": result.schema_version,
        "suite": result.suite,
        "cases": len(result.cases),
        "skippedGraderTypes": list(result.skipped_grader_types),
    }

    row = efficacy_row(
        graded,
        model=model,
        judge_model=None,  # the vendor result never names the model behind its `llm` grader
        measured_on=_today(),
        n_per_arm=n_per_arm,
        ablation=f"{ABLATION_CLAUDE_PLUGIN_EVAL}@{result.schema_version}",
        tokens_per_arm=_tokens_per_arm(result.cases),
        transcripts=0,
        vendor=vendor,
    )
    if notes:
        addendum = "; ".join(notes)
        row_reasoning = f"{row.reasoning}; {addendum}" if row.reasoning else addendum
        row = dataclasses.replace(row, reasoning=row_reasoning)
    return row
