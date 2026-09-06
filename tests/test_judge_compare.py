"""`context-report judge` grades recorded transcripts; `context-report compare` tables the rows."""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path

import pytest

from context_report.efficacy.core import measure
from context_report.efficacy.grade import Graded
from context_report.efficacy.row import efficacy_row
from context_report.efficacy.transcripts import Bundle, RecordingRunner
from context_report.produce.run import produce_statement
from context_report.rows import CLAIMED
from context_report.run import cards as cards_mod
from context_report.run import compare, judge
from context_report.run import manifest as m
from context_report.run.judge_cli import run_judge
from context_report.statement import validate

AGENTS_TEXT = "- Never commit secrets.\n- Always run the tests before pushing.\n"


class FakeRunner:
    """Says whether the rule was present in its prompt; used only to fill the transcript bundle."""

    def __init__(self) -> None:
        self.calls = 0

    def run(self, _task: str, rule: str | None) -> str:
        self.calls += 1
        return "obeyed" if rule else "ignored"


class NeutralJudge:
    """`measure()` needs a Judge while recording; its verdict is never read back."""

    def obeys(self, _rule: str, _task: str, _output: str, _criterion: str) -> bool:
        return True


class FakeAsker:
    """Stands in for the API judge model: YES exactly when the recorded output was "obeyed"."""

    def __init__(self) -> None:
        self.calls = 0

    def ask(self, prompt: str) -> str:
        self.calls += 1
        return "YES" if "obeyed" in prompt else "NO"


def _manifest_doc(out_dir: Path, subjects: dict[str, Path]) -> dict:
    return {
        "contextReportRun": "v0.1",
        "subjects": [
            {"id": sid, "path": str(path), "kind": "instruction-file"}
            for sid, path in subjects.items()
        ],
        "target": {"name": "claude_code"},
        "models": [{"provider": "anthropic", "id": "m"}],
        "tasks": {"tasks": [{"id": "t1", "prompt": "Ship it."}]},
        "arms": {"nPerArm": 2},
        "out": str(out_dir),
    }


def _record_and_produce(
    out_dir: Path, manifest: m.Manifest, subject_id: str, *, record: bool
) -> Path:
    """Write `<subject>/<slug>.json` and its transcripts bundle; `record=False` leaves it empty."""
    subject = manifest.subject(subject_id)
    cards = cards_mod.cards_for(manifest, subject)
    rule_ids = [c.id for c in cards]
    model_ref = manifest.models[0]
    subject_dir = out_dir / subject_id
    subject_dir.mkdir(parents=True, exist_ok=True)
    bundle_root = subject_dir / model_ref.slug / "transcripts"
    if record:
        bundle = Bundle(bundle_root)
        rec = RecordingRunner(
            FakeRunner(), bundle, subject_id=subject_id, model=model_ref.qualified, cards=cards
        )
        for card in cards:
            measure(card, rec, NeutralJudge(), trials=manifest.arms.n_per_arm)
    else:
        bundle_root.mkdir(parents=True)
    bundle = Bundle(bundle_root)

    row = efficacy_row(
        Graded(ungraded=tuple(rule_ids)),
        model=model_ref.qualified,
        judge_model=None,
        measured_on="2026-09-05",
        n_per_arm=manifest.arms.n_per_arm,
        tokens_per_arm={
            "with": {"inputTokens": 10, "outputTokens": 20},
            "without": {"inputTokens": 5, "outputTokens": 15},
        },
        transcripts=4 * len(rule_ids),
    )
    row = dataclasses.replace(
        row, values={**row.values, "unexercised": [f"{subject_id}-unexercised-rule"]}
    )
    stmt = produce_statement(
        subject=subject.path,
        subject_kind="instruction-file",
        target="claude_code",
        efficacy_row=row,
        byproducts=[bundle.descriptor("transcripts")],
    )
    stmt_path = subject_dir / f"{model_ref.slug}.json"
    stmt_path.write_text(json.dumps(stmt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return stmt_path


def _one_subject_run(tmp_path: Path, *, record: bool = True) -> tuple[Path, m.Manifest]:
    agents = tmp_path / "AGENTS.md"
    agents.write_text(AGENTS_TEXT)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "manifest.json").write_text(json.dumps(_manifest_doc(out_dir, {"rules": agents})))
    manifest = m.load(out_dir / "manifest.json")
    _record_and_produce(out_dir, manifest, "rules", record=record)
    return out_dir, manifest


def _two_subject_run(tmp_path: Path) -> tuple[Path, m.Manifest]:
    """subj-a is fully recorded; subj-b's bundle is empty, so judging it will always be skipped."""
    a = tmp_path / "A.md"
    b = tmp_path / "B.md"
    a.write_text(AGENTS_TEXT)
    b.write_text(AGENTS_TEXT)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    doc = _manifest_doc(out_dir, {"subj-a": a, "subj-b": b})
    (out_dir / "manifest.json").write_text(json.dumps(doc))
    manifest = m.load(out_dir / "manifest.json")
    _record_and_produce(out_dir, manifest, "subj-a", record=True)
    _record_and_produce(out_dir, manifest, "subj-b", record=False)
    return out_dir, manifest


# --------------------------------------------------------------------------------------- judge --


def test_judge_writes_judged_statement_and_leaves_the_original_untouched(tmp_path: Path) -> None:
    out_dir, manifest = _one_subject_run(tmp_path)
    slug = manifest.models[0].slug
    stmt_path = out_dir / "rules" / f"{slug}.json"
    original_bytes = stmt_path.read_bytes()

    fake_asker = FakeAsker()
    outcomes, code = judge.judge_out(
        out_dir, "anthropic/j", asker_factory=lambda _model_id: fake_asker
    )

    assert code == 0
    assert len(outcomes) == 1
    assert outcomes[0].judged and outcomes[0].subject_id == "rules"
    assert stmt_path.read_bytes() == original_bytes, "the un-judged report is a record"

    judged_path = out_dir / "rules" / f"{slug}.judged.json"
    assert judged_path.is_file()
    judged_stmt = json.loads(judged_path.read_text(encoding="utf-8"))
    eff = next(a for a in judged_stmt["predicate"]["attributes"] if a["attribute"] == "efficacy")
    assert eff["basis"] == CLAIMED
    assert eff["conditions"]["judgeModel"] == "anthropic/j"
    assert eff["conditions"]["judge"] == "model"
    assert eff["values"]["tokensPerArm"]["with"] == {"inputTokens": 10, "outputTokens": 20}
    assert eff["values"]["unexercised"] == ["rules-unexercised-rule"]
    assert validate(judged_stmt) == []
    assert fake_asker.calls > 0


def test_judge_on_an_empty_bundle_skips_the_statement_and_exits_1(tmp_path: Path) -> None:
    out_dir, _manifest = _one_subject_run(tmp_path, record=False)
    fake_asker = FakeAsker()
    outcomes, code = judge.judge_out(
        out_dir, "anthropic/j", asker_factory=lambda _model_id: fake_asker
    )
    assert code == 1
    assert len(outcomes) == 1
    assert not outcomes[0].judged
    assert "did not record" in outcomes[0].message
    assert fake_asker.calls == 0
    assert not list((out_dir / "rules").glob("*.judged.json"))


def test_non_anthropic_judge_is_refused_before_any_asker_call(tmp_path: Path) -> None:
    out_dir, _manifest = _one_subject_run(tmp_path)
    calls: list[str] = []
    with pytest.raises(ValueError, match="anthropic"):
        judge.judge_out(out_dir, "openai/gpt-4", asker_factory=calls.append)
    assert calls == []


def test_run_judge_cli_exits_2_for_an_unsupported_provider(tmp_path: Path) -> None:
    out_dir, _manifest = _one_subject_run(tmp_path)
    args = argparse.Namespace(out=str(out_dir), judge="openai/gpt-4")
    assert run_judge(args) == 2


# ------------------------------------------------------------------------------------- compare --


def test_compare_table_has_subject_model_and_lift_by_model(tmp_path: Path) -> None:
    out_dir, manifest = _two_subject_run(tmp_path)
    fake_asker = FakeAsker()
    outcomes, code = judge.judge_out(
        out_dir, "anthropic/j", asker_factory=lambda _model_id: fake_asker
    )
    assert code == 0  # subj-a was judged even though subj-b (empty bundle) was skipped
    assert {o.subject_id: o.judged for o in outcomes} == {"subj-a": True, "subj-b": False}

    judged = json.loads((out_dir / "subj-a" / f"{manifest.models[0].slug}.judged.json").read_text())
    eff = next(a for a in judged["predicate"]["attributes"] if a["attribute"] == "efficacy")
    lift_text = f"{eff['estimate']['pointEstimate']:+.2f}"

    table = compare.render_table(out_dir, by="model", judged=True)
    assert "subj-a" in table and "subj-b" in table
    assert manifest.models[0].qualified in table
    assert lift_text in table
    assert "(unjudged)" in table  # subj-b fell back to its un-judged statement
    assert table.splitlines()[0].startswith("model")
    assert "100" in table  # tokens/arm: both subjects, both arms, input and output, not 0

    transposed = compare.render_table(out_dir, by="subject", judged=True)
    assert transposed.splitlines()[0].startswith("subject")
    assert transposed != table

    # subj-a's rules all got graded by the judge, so nothing is left ungraded there; subj-b's
    # statement was never judged, so its rules are still all reported ungraded.
    assert "subj-b:" in table
    assert "ungraded:" in table
    assert "unexercised: subj-a-unexercised-rule" in table
    assert "unexercised: subj-b-unexercised-rule" in table


def test_compare_by_by_argument_is_validated(tmp_path: Path) -> None:
    out_dir, _manifest = _one_subject_run(tmp_path)
    with pytest.raises(ValueError, match="--by"):
        compare.render_table(out_dir, by="bogus")


def test_compare_with_no_recorded_statements_says_so(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    assert "no recorded statements" in compare.render_table(out_dir)
