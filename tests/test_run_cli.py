"""`context-report run`: the fixed output layout, end to end, against a fake backend."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from context_report import statement as statement_mod
from context_report.efficacy.transcripts import Bundle
from context_report.rows import CLAIMED, NOT_AVAILABLE
from context_report.run import cli as cli_mod
from context_report.run import compare, layout
from context_report.run import manifest as m
from context_report.run.cards import cards_for
from context_report.run.cli import add_run_parser, run_run
from context_report.run.runner import RunError, preflight, run

PRINT_RULE_TEXT = "No print statements in shipped code."
SECRET_RULE_TEXT = "Never commit secrets to the repository."  # noqa: S105 -- rule text, not a secret
WITH_MARKER = "Follow this rule strictly:"


class FakeAsker:
    """Canned outputs keyed on the arm; a call is never sent to a real model."""

    def __init__(self) -> None:
        self.calls = 0
        self.last_usage = {"inputTokens": 10, "outputTokens": 20}

    def ask(self, prompt: str) -> str:
        self.calls += 1
        if prompt.startswith(WITH_MARKER):
            rule_part = prompt.split("Task:", maxsplit=1)[0].lower()
            if "print" in rule_part:
                return "```python\ndef f():\n    logging.info('done')\n```"  # obeys
            return "```python\ndef f():\n    print('leaked')\n```"  # never actually judged
        return "```python\ndef f():\n    print('debug')\n```"  # without-arm: model already prints


def _fake_asker_factory(askers: list[FakeAsker]):
    def factory(model, *, effort=None, cwd=None):  # noqa: ARG001 -- Asker factory contract
        asker = FakeAsker()
        asker.cwd = cwd
        askers.append(asker)
        return asker

    return factory


def _write_subject(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text(f"- {PRINT_RULE_TEXT}\n- {SECRET_RULE_TEXT}\n")


def _base_doc() -> dict:
    return {
        "contextReportRun": "v0.1",
        "subjects": [{"id": "house-rules", "path": "./AGENTS.md", "kind": "instruction-file"}],
        "target": {"name": "claude_code", "clientVersion": "2.1.0"},
        "models": [{"provider": "anthropic", "id": "claude-sonnet-5"}],
        "tasks": "tasks.json",
        "arms": {"nPerArm": 2, "seed": 1, "mode": "isolated"},
        "judge": None,
        "out": "out",
    }


def _rule_ids(tmp_path: Path) -> list[str]:
    """Extraction order of AGENTS.md's two bullets: [print-rule, secrets-rule]."""
    _write_subject(tmp_path)
    probe_tasks = {"tasks": [{"id": "probe", "prompt": "Ship."}]}
    (tmp_path / "tasks.json").write_text(json.dumps(probe_tasks))
    (tmp_path / "run.json").write_text(json.dumps(_base_doc()))
    probe = m.load(tmp_path / "run.json")
    return [c.id for c in cards_for(probe, probe.subject("house-rules"))]


def _build_manifest(tmp_path: Path, *, provider: str = "anthropic") -> m.Manifest:
    print_id, _secret_id = _rule_ids(tmp_path)
    tasks = {
        "tasks": [
            {
                "id": "no-print-task",
                "prompt": "Write a debug helper function.",
                "rules": [print_id],
                "criteria": {print_id: PRINT_RULE_TEXT},
            },
            {"id": "general-task", "prompt": "Refactor the module for clarity."},
        ]
    }
    (tmp_path / "tasks.json").write_text(json.dumps(tasks))
    doc = _base_doc()
    doc["models"] = [{"provider": provider, "id": "claude-sonnet-5"}]
    (tmp_path / "run.json").write_text(json.dumps(doc))
    return m.load(tmp_path / "run.json")


def test_output_layout_and_statements_validate(tmp_path: Path) -> None:
    manifest = _build_manifest(tmp_path)
    askers: list[FakeAsker] = []
    out = run(manifest, asker_factory=_fake_asker_factory(askers))

    assert out == manifest.out / "runs" / out.name  # every run gets its own directory
    assert (out / "manifest.json").is_file()
    assert (out / "SUMMARY.md").is_file()
    stmt_path = out / "house-rules" / "anthropic--claude-sonnet-5.json"
    assert stmt_path.is_file()
    transcripts_dir = out / "house-rules" / "anthropic--claude-sonnet-5" / "transcripts"
    assert transcripts_dir.is_dir()
    assert list(transcripts_dir.glob("*.json")), "expected recorded transcripts"

    manifest_doc = json.loads((out / "manifest.json").read_text())
    assert manifest_doc["subjects"][0]["path"] == str(manifest.subjects[0].path)
    assert manifest_doc["arms"] == {"nPerArm": 2, "seed": 1, "mode": "isolated"}

    stmt = json.loads(stmt_path.read_text())
    assert statement_mod.validate(stmt) == []
    rows = {r["attribute"]: r for r in stmt["predicate"]["attributes"]}
    efficacy = rows["efficacy"]
    assert efficacy["basis"] == CLAIMED
    assert efficacy["conditions"]["model"] == "anthropic/claude-sonnet-5"
    assert efficacy["conditions"]["judgeModel"] is None
    assert "tokensPerArm" in efficacy["values"]
    assert efficacy["values"]["tokensPerArm"]["with"]["inputTokens"] > 0

    byproducts = stmt["predicate"]["byproducts"]
    assert byproducts[0]["digest"]["sha256"] == Bundle(transcripts_dir).digest()

    assert askers, "the fake asker factory should have been used"


def test_dry_run_makes_zero_asker_calls_and_prints_budget(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _build_manifest(tmp_path)  # writes run.json/tasks.json as a side effect
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    add_run_parser(sub)
    args = parser.parse_args(["run", str(tmp_path / "run.json"), "--dry-run"])
    assert run_run(args) == 0
    out = capsys.readouterr().out
    assert "model call(s)" in out
    assert "judge: none" in out


def test_non_anthropic_provider_yields_not_available_row_and_no_transcripts(
    tmp_path: Path,
) -> None:
    manifest = _build_manifest(tmp_path, provider="openai")
    out = run(manifest, asker_factory=_fake_asker_factory([]))
    stmt_path = out / "house-rules" / "openai--claude-sonnet-5.json"
    stmt = json.loads(stmt_path.read_text())
    efficacy = next(r for r in stmt["predicate"]["attributes"] if r["attribute"] == "efficacy")
    assert efficacy["result"] == NOT_AVAILABLE
    assert "no backend" in efficacy["reasoning"]
    assert not (out / "house-rules" / "openai--claude-sonnet-5" / "transcripts").exists()


def test_leave_one_out_exits_2_with_no_asker_calls(tmp_path: Path) -> None:
    manifest = _build_manifest(tmp_path)
    doc = json.loads((tmp_path / "run.json").read_text())
    doc["arms"]["mode"] = "leave-one-out"
    (tmp_path / "run.json").write_text(json.dumps(doc))

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    add_run_parser(sub)
    args = parser.parse_args(["run", str(tmp_path / "run.json")])
    assert run_run(args) == 2
    assert not manifest.out.exists()


def test_invalid_manifest_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "run.json").write_text(json.dumps({"contextReportRun": "v0.1"}))
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    add_run_parser(sub)
    args = parser.parse_args(["run", str(tmp_path / "run.json")])
    assert run_run(args) == 2
    assert "error:" in capsys.readouterr().err


def test_claude_cli_provider_runs_the_arms(tmp_path: Path) -> None:
    """`claude-cli/<alias>` is a real backend: arms run, transcripts recorded, row measured."""
    manifest = _build_manifest(tmp_path, provider="claude-cli")
    askers: list[FakeAsker] = []
    out = run(manifest, asker_factory=_fake_asker_factory(askers))
    stmt = json.loads((out / "house-rules" / "claude-cli--claude-sonnet-5.json").read_text())
    efficacy = next(a for a in stmt["predicate"]["attributes"] if a["attribute"] == "efficacy")
    assert efficacy["conditions"]["model"] == "claude-cli/claude-sonnet-5"
    assert efficacy["result"] != "NotAvailable" or "no backend" not in efficacy["reasoning"]
    assert askers, "the factory was used for the claude-cli provider"


def test_resume_keeps_finished_pairs_and_only_fills_the_gaps(tmp_path: Path) -> None:
    """A killed run is picked up where it stopped: no model call for what is already on disk."""
    manifest = _build_manifest(tmp_path)
    askers: list[FakeAsker] = []
    out = run(manifest, asker_factory=_fake_asker_factory(askers))
    first_calls = sum(a.calls for a in askers)
    stmt_path = out / "house-rules" / "anthropic--claude-sonnet-5.json"
    before = stmt_path.read_text()
    summary_before = (out / "SUMMARY.md").read_text()

    askers.clear()
    assert run(manifest, asker_factory=_fake_asker_factory(askers), resume=True) == out
    assert sum(a.calls for a in askers) == 0
    assert stmt_path.read_text() == before
    assert (out / "SUMMARY.md").read_text() == summary_before

    # A pair with transcripts but no statement re-runs, reusing what matches on disk.
    stmt_path.unlink()
    transcripts_dir = out / "house-rules" / "anthropic--claude-sonnet-5" / "transcripts"
    recorded = sorted(transcripts_dir.glob("*.json"))
    recorded[-1].unlink()
    askers.clear()
    run(manifest, asker_factory=_fake_asker_factory(askers), resume=True)
    assert sum(a.calls for a in askers) == 1
    assert stmt_path.is_file()
    assert len(list(transcripts_dir.glob("*.json"))) == len(recorded)
    assert first_calls == len(recorded)


def test_run_cli_accepts_resume() -> None:
    parser = argparse.ArgumentParser()
    add_run_parser(parser.add_subparsers(dest="command"))
    args = parser.parse_args(["run", "run.json", "--resume"])
    assert args.resume is True


def test_every_run_is_kept_and_laid_side_by_side(tmp_path: Path) -> None:
    """Two runs of one manifest: two directories, an index, and a history table across both."""
    manifest = _build_manifest(tmp_path)
    first = run(manifest, asker_factory=_fake_asker_factory([]), run_id="r1")
    second = run(manifest, asker_factory=_fake_asker_factory([]), run_id="r2")
    assert first != second and first.is_dir() and second.is_dir()
    assert layout.run_ids(manifest.out) == ["r1", "r2"]

    index = json.loads((manifest.out / "runs.json").read_text())
    assert [e["runId"] for e in index] == ["r1", "r2"]
    assert index[0]["rows"][0]["subject"] == "house-rules"
    history = (manifest.out / "SUMMARY.md").read_text()
    assert "| r1 | r2 |" in history and "house-rules" in history
    assert compare.render_history(manifest.out) == history

    with pytest.raises(RunError, match="already exists"):
        run(manifest, asker_factory=_fake_asker_factory([]), run_id="r2")
    assert layout.resolve_run_dir(manifest.out) == second  # the latest, by id order
    assert layout.resolve_run_dir(manifest.out, "r1") == first
    assert "anthropic/claude-sonnet-5" in compare.render_table(manifest.out, run_id="r1")


def test_a_flat_pre_history_layout_still_reads_as_one_run(tmp_path: Path) -> None:
    flat = tmp_path / "flat"
    flat.mkdir()
    (flat / "manifest.json").write_text("{}")
    assert layout.resolve_run_dir(flat) == flat
    with pytest.raises(ValueError, match="no run found"):
        layout.resolve_run_dir(tmp_path / "nowhere")


def test_run_cli_reports_the_run_directory(tmp_path: Path) -> None:
    manifest = _build_manifest(tmp_path)
    parser = argparse.ArgumentParser()
    add_run_parser(parser.add_subparsers(dest="command"))
    args = parser.parse_args(["run", str(tmp_path / "run.json"), "--run-id", "smoke"])
    assert args.run_id == "smoke" and args.resume is False
    (manifest.out / "runs" / "smoke").mkdir(parents=True)
    (manifest.out / "runs" / "smoke" / "SUMMARY.md").write_text("| table |\n")
    text = cli_mod._report(manifest.out / "runs" / "smoke", manifest.out)
    assert text.startswith("run smoke: ") and "| table |" in text


def test_workdir_reaches_the_backend_and_the_resolved_manifest(tmp_path: Path) -> None:
    """`subjects[].workdir` is where the subject model works; the run records it, resolved."""
    manifest = _build_manifest(tmp_path, provider="claude-cli")
    repo = tmp_path / "checkout"
    repo.mkdir()
    doc = json.loads((tmp_path / "run.json").read_text())
    doc["subjects"][0]["workdir"] = "checkout"
    (tmp_path / "run.json").write_text(json.dumps(doc))
    manifest = m.load(tmp_path / "run.json")
    assert manifest.subjects[0].workdir == repo.resolve()

    askers: list[FakeAsker] = []
    out = run(manifest, asker_factory=_fake_asker_factory(askers))
    assert {a.cwd for a in askers} == {repo.resolve()}
    recorded = json.loads((out / "manifest.json").read_text())
    assert recorded["subjects"][0]["workdir"] == str(repo.resolve())


def test_workdir_must_exist_and_the_api_provider_cannot_honour_it(tmp_path: Path) -> None:
    _build_manifest(tmp_path, provider="claude-cli")
    doc = json.loads((tmp_path / "run.json").read_text())
    doc["subjects"][0]["workdir"] = "missing"
    (tmp_path / "run.json").write_text(json.dumps(doc))
    with pytest.raises(m.ManifestError, match="workdir is not a directory"):
        m.load(tmp_path / "run.json")

    (tmp_path / "missing").mkdir()
    doc["models"] = [{"provider": "anthropic", "id": "claude-sonnet-5"}]
    (tmp_path / "run.json").write_text(json.dumps(doc))
    with pytest.raises(RunError, match="cannot honour"):
        preflight(m.load(tmp_path / "run.json"))
