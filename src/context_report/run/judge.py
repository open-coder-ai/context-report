"""Grade recorded transcripts with a judge model, without re-running any arm."""

from __future__ import annotations

import copy
import dataclasses
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from context_report.efficacy.backends import Asker, AskerJudge
from context_report.efficacy.grade import grade
from context_report.efficacy.row import VALUES_UNEXERCISED, efficacy_row
from context_report.efficacy.transcripts import Bundle, MissingTranscriptError, ReplayRunner
from context_report.run.cards import cards_for
from context_report.run.manifest import Manifest
from context_report.run.manifest import load as load_manifest
from context_report.statement import now_utc
from context_report.statement import validate as validate_statement

ANTHROPIC = "anthropic"
AskerFactory = Callable[[str], Asker]


class UnsupportedJudgeProviderError(ValueError):
    """`--judge` names a provider v0.1 has no judge backend for."""


def parse_judge_ref(spec: str) -> tuple[str, str]:
    """Split `provider/id`; raise if malformed or the provider has no v0.1 judge backend."""
    provider, sep, model_id = spec.partition("/")
    if not sep or not provider or not model_id:
        raise ValueError(f"--judge must be provider/id, not {spec!r}")
    if provider != ANTHROPIC:
        raise UnsupportedJudgeProviderError(
            f"--judge provider {provider!r} has no backend in v0.1 (only {ANTHROPIC!r})"
        )
    return provider, model_id


def _default_asker_factory(model_id: str) -> Asker:
    # Lazy: importing api_backend imports `anthropic`, which most callers of this module never need.
    from context_report.efficacy.api_backend import JUDGE_EFFORT, ApiAsker

    return ApiAsker(model_id, effort=JUDGE_EFFORT)


@dataclasses.dataclass(frozen=True)
class JudgeOutcome:
    """One statement's judging attempt: enough for the CLI's one-line-per-statement report."""

    subject_id: str
    model: str
    judged: bool
    message: str
    row: dict[str, Any] | None = None


def _efficacy_attribute(stmt: dict[str, Any]) -> dict[str, Any]:
    return next(a for a in stmt["predicate"]["attributes"] if a["attribute"] == "efficacy")


@dataclasses.dataclass(frozen=True)
class _StatementRef:
    """One recorded statement worth attempting: which subject, which model, where it lives."""

    subject_id: str
    slug: str
    path: Path


def _statement_files(out: Path, manifest: Manifest) -> list[_StatementRef]:
    """A ref for every recorded statement that has a transcripts bundle to replay."""
    found: list[_StatementRef] = []
    for subject in manifest.subjects:
        subject_dir = out / subject.id
        if not subject_dir.is_dir():
            continue
        for stmt_path in sorted(subject_dir.glob("*.json")):
            slug = stmt_path.stem
            if slug == "statement" or slug.endswith(".judged"):
                continue  # the no-models placeholder, or a judged file from an earlier run
            if (subject_dir / slug / "transcripts").is_dir():
                found.append(_StatementRef(subject.id, slug, stmt_path))
    return found


def _judge_one(
    manifest: Manifest, ref: _StatementRef, judge_model: str, aj: AskerJudge
) -> JudgeOutcome:
    subject = manifest.subject(ref.subject_id)
    stmt = json.loads(ref.path.read_text(encoding="utf-8"))
    existing = _efficacy_attribute(stmt)
    model = existing.get("conditions", {}).get("model", ref.slug)
    existing_values = existing.get("values") or {}
    cards = cards_for(manifest, subject)
    transcripts_dir = ref.path.parent / ref.slug / "transcripts"
    runner = ReplayRunner(Bundle(transcripts_dir), cards)
    try:
        graded = grade(cards, runner, aj, trials=manifest.arms.n_per_arm)
    except MissingTranscriptError as exc:
        msg = f"the run did not record that arm: {exc}"
        return JudgeOutcome(ref.subject_id, model, judged=False, message=msg)

    row = efficacy_row(
        graded,
        model=model,
        judge_model=judge_model,
        measured_on=now_utc()[:10],
        n_per_arm=manifest.arms.n_per_arm,
        tokens_per_arm=existing_values.get("tokensPerArm"),
        transcripts=sum(1 for _ in transcripts_dir.glob("*.json")),
        unexercised=existing_values.get(VALUES_UNEXERCISED) or (),  # a fact about the subject
    )

    judged_stmt = copy.deepcopy(stmt)
    attrs = judged_stmt["predicate"]["attributes"]
    for i, attr in enumerate(attrs):
        if attr["attribute"] == "efficacy":
            attrs[i] = row.to_dict()
            break
    judged_stmt["predicate"].setdefault("metadata", {})["finishedOn"] = now_utc()
    errors = validate_statement(judged_stmt)
    if errors:  # a bug in this module, never a user error
        raise ValueError(f"judged statement failed its own schema: {'; '.join(errors)}")

    judged_path = ref.path.with_name(f"{ref.slug}.judged.json")
    judged_path.write_text(
        json.dumps(judged_stmt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return JudgeOutcome(ref.subject_id, model, judged=True, message="judged", row=row.to_dict())


def judge_out(
    out: Path, judge_spec: str, *, asker_factory: AskerFactory = _default_asker_factory
) -> tuple[list[JudgeOutcome], int]:
    """Grade every recorded statement under `out`; returns outcomes and the process exit code.

    Exit stays 0 even when some statements were skipped (the run recorded no arm for them, e.g.
    a non-anthropic model) -- only when *nothing at all* could be judged does it become 1.
    """
    provider, model_id = parse_judge_ref(judge_spec)  # before anything: no manifest, no asker
    manifest = load_manifest(out / "manifest.json")
    aj = AskerJudge(asker_factory(model_id))
    judge_model = f"{provider}/{model_id}"
    outcomes = [
        _judge_one(manifest, ref, judge_model, aj) for ref in _statement_files(out, manifest)
    ]
    code = 0 if any(o.judged for o in outcomes) else 1
    return outcomes, code
