"""Execute a run manifest: fixed output layout, recorded arms per (subject, model) pair."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from context_report.efficacy.api_backend import JUDGE_EFFORT, ApiAsker
from context_report.efficacy.backends import Asker, AskerJudge, AskerRunner
from context_report.efficacy.core import RuleCard
from context_report.efficacy.grade import Graded, grade
from context_report.efficacy.row import ATTRIBUTE as EFFICACY
from context_report.efficacy.row import efficacy_row
from context_report.efficacy.transcripts import Bundle, RecordingRunner
from context_report.produce.run import produce_statement
from context_report.rows import Row
from context_report.run.cards import cards_for, unexercised_rules
from context_report.run.evalcases import checkers_for
from context_report.run.manifest import MODE_LEAVE_ONE_OUT, Manifest, ModelRef, Subject

ANTHROPIC = "anthropic"
CLAUDE_CLI = "claude-cli"
PROVIDERS = (ANTHROPIC, CLAUDE_CLI)  # the API with a key; the local Claude Code CLI with its login
MANIFEST_FILENAME = "manifest.json"
SUMMARY_FILENAME = "SUMMARY.md"

# (model, *, effort) -> Asker; tests inject a fake so no network call is ever made.
AskerFactory = Callable[..., Asker]


class RunError(ValueError):
    """A manifest is well-formed but asks for something v0.1's engine cannot do."""


def default_asker_factory(model: ModelRef, *, effort: str | None = None) -> Asker:
    """The real backends, built only for a provider actually used: the API, or the `claude` CLI."""
    if model.provider == CLAUDE_CLI:
        from context_report.efficacy.cli_backend import CliAsker  # noqa: PLC0415

        return CliAsker(model=model.id)  # the CLI has no effort knob; the judge runs as-is
    return ApiAsker(model.id, effort=effort)


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _resolved_manifest_doc(manifest: Manifest) -> dict[str, Any]:
    """`out/manifest.json`: absolute paths, tasks inlined, defaults filled in."""

    return {
        "contextReportRun": "v0.1",
        "subjects": [{"id": s.id, "path": str(s.path), "kind": s.kind} for s in manifest.subjects],
        "target": {"name": manifest.target.name, "clientVersion": manifest.target.client_version},
        "models": [{"provider": m.provider, "id": m.id} for m in manifest.models],
        "tasks": [
            {
                "id": t.id,
                "prompt": t.prompt,
                "subjects": list(t.subjects),
                "rules": list(t.rules),
                "criteria": t.criteria,
            }
            for t in manifest.tasks
        ],
        "arms": {
            "nPerArm": manifest.arms.n_per_arm,
            "seed": manifest.arms.seed,
            "mode": manifest.arms.mode,
        },
        "judge": {"provider": manifest.judge.provider, "id": manifest.judge.id}
        if manifest.judge
        else None,
        "out": str(manifest.out),
    }


def _call_budget(cards: list[RuleCard], n_per_arm: int) -> int:
    """Model calls one (subject, model) pair would spend: each scenario, both arms, n trials."""
    return sum(len(c.scenarios) for c in cards) * 2 * n_per_arm


def preflight(manifest: Manifest) -> None:
    """Reject what v0.1 cannot run at all, before a single call is made."""
    if manifest.arms.mode == MODE_LEAVE_ONE_OUT:
        raise RunError("arms.mode 'leave-one-out' is not implemented in v0.1; use 'isolated'")
    if manifest.judge is not None and manifest.judge.provider not in PROVIDERS:
        raise RunError(
            f"no backend for judge provider {manifest.judge.provider!r} in v0.1 (have {PROVIDERS})"
        )


def dry_run_report(manifest: Manifest) -> str:
    """What `--dry-run` prints: rules found/exercised, and the call budget, no model touched."""
    judge = manifest.judge.qualified if manifest.judge else "none (deterministic criteria only)"
    lines = [f"judge: {judge}"]
    for subject in manifest.subjects:
        cards = cards_for(manifest, subject)
        unexercised = unexercised_rules(manifest, subject)
        lines.append("")
        lines.append(
            f"{subject.id} ({subject.kind}): {len(cards) + len(unexercised)} rule(s) found, "
            f"{len(cards)} exercised"
        )
        lines.append(f"  unexercised: {', '.join(unexercised) if unexercised else '(none)'}")
        for model in manifest.models:
            budget = _call_budget(cards, manifest.arms.n_per_arm)
            lines.append(f"  {model.qualified}: {budget} model call(s)")
    return "\n".join(lines)


def _no_backend_row(  # noqa: PLR0913 -- keyword-only; these are the row's own conditions
    cards: list[RuleCard],
    unexercised: list[str],
    *,
    model: ModelRef,
    judge_model: str | None,
    measured_on: str,
    n_per_arm: int,
) -> Row:
    """v0.1 has a backend only for anthropic: no arm runs, and the row says exactly why."""
    graded = Graded(ungraded=tuple(c.id for c in cards))
    row = efficacy_row(
        graded,
        model=model.qualified,
        judge_model=judge_model,
        measured_on=measured_on,
        n_per_arm=n_per_arm,
        transcripts=0,
        unexercised=unexercised,
    )
    return dataclasses.replace(row, reasoning=f"no backend for provider {model.provider!r} in v0.1")


def _row_summary(
    subject_id: str,
    model_label: str,
    row: Row,
    *,
    transcripts: int,
    tokens_per_arm: dict[str, dict[str, int]] | None,
) -> dict[str, Any]:
    estimate = None
    if row.estimate is not None:
        estimate = (row.estimate.point_estimate, row.estimate.lower_bound, row.estimate.upper_bound)
    values = row.values or {}
    return {
        "subject": subject_id,
        "model": model_label,
        "result": row.result,
        "estimate": estimate,
        "graded": len(values.get("perRule", [])),
        "ungraded": len(values.get("ungraded", [])),
        "transcripts": transcripts,
        "tokens_per_arm": tokens_per_arm,
    }


def _run_model(  # noqa: PLR0913, PLR0917 -- one (subject, model) pair needs all of this context
    manifest: Manifest,
    subject: Subject,
    model: ModelRef,
    cards: list[RuleCard],
    unexercised: list[str],
    judge: AskerJudge | None,
    judge_model: str | None,
    model_dir: Path,
    asker_factory: AskerFactory,
    *,
    resume: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run (or skip, for an unsupported provider) one (subject, model) pair."""
    measured_on = _today()
    n_per_arm = manifest.arms.n_per_arm
    if model.provider not in PROVIDERS:
        row = _no_backend_row(
            cards,
            unexercised,
            model=model,
            judge_model=judge_model,
            measured_on=measured_on,
            n_per_arm=n_per_arm,
        )
        stmt = produce_statement(
            subject=subject.path,
            subject_kind=subject.kind,
            target=manifest.target.name,
            client_version=manifest.target.client_version,
            efficacy_row=row,
        )
        summary = _row_summary(subject.id, model.qualified, row, transcripts=0, tokens_per_arm=None)
        return stmt, summary

    bundle = Bundle(model_dir / "transcripts")
    asker = asker_factory(model, effort=None)
    rec = RecordingRunner(
        AskerRunner(asker),
        bundle,
        subject_id=subject.id,
        model=model.qualified,
        cards=cards,
        resume=resume,
    )
    checkers = checkers_for(manifest.tasks_for(subject.id), cards)
    graded = grade(cards, rec, judge, trials=n_per_arm, checkers=checkers)
    transcripts = len(list(bundle.root.glob("*.json"))) if bundle.root.exists() else 0
    row = efficacy_row(
        graded,
        model=model.qualified,
        judge_model=judge_model,
        measured_on=measured_on,
        n_per_arm=n_per_arm,
        tokens_per_arm=rec.tokens_per_arm,
        transcripts=transcripts,
        unexercised=unexercised,
    )
    stmt = produce_statement(
        subject=subject.path,
        subject_kind=subject.kind,
        target=manifest.target.name,
        client_version=manifest.target.client_version,
        efficacy_row=row,
        byproducts=[bundle.descriptor("transcripts")],
    )
    summary = _row_summary(
        subject.id, model.qualified, row, transcripts=transcripts, tokens_per_arm=rec.tokens_per_arm
    )
    return stmt, summary


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _tokens_cell(tokens_per_arm: dict[str, dict[str, int]] | None) -> str:
    if tokens_per_arm is None:
        return "n/a"
    w, wo = tokens_per_arm.get("with", {}), tokens_per_arm.get("without", {})
    return (
        f"with in={w.get('inputTokens', 0)}/out={w.get('outputTokens', 0)}; "
        f"without in={wo.get('inputTokens', 0)}/out={wo.get('outputTokens', 0)}"
    )


_SUMMARY_HEADER = (
    "| subject | model | result | lift (95% CI) | graded/ungraded | transcripts | tokens per arm |"
)
_SUMMARY_SEP = "|---|---|---|---|---|---|---|"


def _summary_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [_SUMMARY_HEADER, _SUMMARY_SEP]
    for r in rows:
        lift = "n/a"
        if r["estimate"] is not None:
            point, lower, upper = r["estimate"]
            lift = f"{point:+.1%} [{lower:+.1%}, {upper:+.1%}]"
        tokens = _tokens_cell(r["tokens_per_arm"])
        lines.append(
            f"| {r['subject']} | {r['model']} | {r['result']} | {lift} | "
            f"{r['graded']}/{r['ungraded']} | {r['transcripts']} | {tokens} |"
        )
    return "\n".join(lines) + "\n"


def _finished_summary(
    subject_id: str, model: ModelRef, path: Path, model_dir: Path
) -> dict[str, Any]:
    """The summary row of a (subject, model) pair whose statement `path` an earlier run wrote."""
    stmt = json.loads(path.read_text(encoding="utf-8"))
    rows = [a for a in stmt["predicate"]["attributes"] if a["attribute"] == EFFICACY]
    values = rows[0].get("values", {}) if rows else {}
    estimate = None
    ci = (rows[0].get("estimate") or {}) if rows else {}
    if ci:
        bounds = ci.get("confidenceInterval", {})
        estimate = (ci["pointEstimate"], bounds.get("lowerBound"), bounds.get("upperBound"))
    transcripts_dir = model_dir / "transcripts"
    return {
        "subject": subject_id,
        "model": model.qualified,
        "result": rows[0]["result"] if rows else "NotAvailable",
        "estimate": estimate,
        "graded": len(values.get("perRule", [])),
        "ungraded": len(values.get("ungraded", [])),
        "transcripts": len(list(transcripts_dir.glob("*.json"))) if transcripts_dir.exists() else 0,
        "tokens_per_arm": values.get("tokensPerArm"),
    }


def run(
    manifest: Manifest,
    *,
    asker_factory: AskerFactory = default_asker_factory,
    resume: bool = False,
) -> None:
    """Run every subject and model of `manifest`, writing the fixed output layout under `out`.

    With `resume`, a pair whose statement already exists under `out` is kept as is, and a pair
    whose transcripts are partly on disk reuses every transcript whose input hash still matches.
    """
    preflight(manifest)
    judge_model = manifest.judge.qualified if manifest.judge else None
    judge = None
    if manifest.judge is not None:
        judge = AskerJudge(asker_factory(manifest.judge, effort=JUDGE_EFFORT))

    out = manifest.out
    out.mkdir(parents=True, exist_ok=True)
    _write_json(out / MANIFEST_FILENAME, _resolved_manifest_doc(manifest))

    summary_rows: list[dict[str, Any]] = []
    for subject in manifest.subjects:
        subject_dir = out / subject.id
        cards = cards_for(manifest, subject)
        unexercised = unexercised_rules(manifest, subject)
        if not manifest.models:
            stmt = produce_statement(
                subject=subject.path,
                subject_kind=subject.kind,
                target=manifest.target.name,
                client_version=manifest.target.client_version,
            )
            _write_json(subject_dir / "statement.json", stmt)
            continue
        for model in manifest.models:
            stmt_path = subject_dir / f"{model.slug}.json"
            if resume and stmt_path.exists():
                summary_rows.append(
                    _finished_summary(subject.id, model, stmt_path, subject_dir / model.slug)
                )
                continue
            stmt, summary = _run_model(
                manifest,
                subject,
                model,
                cards,
                unexercised,
                judge,
                judge_model,
                subject_dir / model.slug,
                asker_factory,
                resume=resume,
            )
            _write_json(stmt_path, stmt)
            summary_rows.append(summary)

    (out / SUMMARY_FILENAME).write_text(_summary_markdown(summary_rows), encoding="utf-8")
