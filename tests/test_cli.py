"""The CLI: exit codes, JSON output, and that it never prints a verdict about the artifact."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from context_report.cli import main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = json.loads(
    (ROOT / "spec/attestation/v0.1/examples/plugin-copilot.json").read_text(encoding="utf-8")
)


def _write_statement(tmp_path: Path, stmt: dict, name: str = "statement.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(stmt), encoding="utf-8")
    return path


def test_verify_exits_zero_for_a_well_formed_statement(tmp_path, capsys):
    path = _write_statement(tmp_path, EXAMPLE)
    code = main(["verify", str(path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "efficacy" in out
    assert "(author-reported)" in out


def test_verify_exits_one_for_schema_errors_and_surfaces_them(tmp_path, capsys):
    bad = copy.deepcopy(EXAMPLE)
    bad["predicateType"] = "https://example.com/other/v1"
    path = _write_statement(tmp_path, bad)

    code = main(["verify", str(path)])
    out = capsys.readouterr().out
    assert code == 1
    assert "schema error" in out.lower()


def test_verify_exits_one_on_subject_digest_mismatch(tmp_path, capsys):
    artifact = tmp_path / "hook.sh"
    artifact.write_text("#!/bin/sh\nexit 0\n")
    stmt = copy.deepcopy(EXAMPLE)  # subject digest in the example does not match this artifact

    path = _write_statement(tmp_path, stmt)
    code = main(["verify", str(path), "--subject", str(artifact)])
    out = capsys.readouterr().out
    assert code == 1
    assert "MISMATCH" in out


def test_verify_exits_two_for_a_missing_statement_file(tmp_path, capsys):
    missing = tmp_path / "does-not-exist.json"
    code = main(["verify", str(missing)])
    err = capsys.readouterr().err
    assert code == 2
    assert str(missing) in err


def test_verify_exits_two_for_malformed_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    assert main(["verify", str(path)]) == 2


def test_missing_command_is_a_usage_error():
    assert main([]) == 2


def test_unknown_command_is_a_usage_error():
    assert main(["frobnicate"]) == 2


def test_json_flag_is_parseable_and_matches_the_human_summary(tmp_path, capsys):
    path = _write_statement(tmp_path, EXAMPLE)
    code = main(["verify", str(path), "--json"])
    out = capsys.readouterr().out
    assert code == 0

    payload = json.loads(out)
    assert payload["ok"] is True
    assert payload["claimed"] == ["efficacy"]
    assert payload["schema_errors"] == []
    assert any(r["attribute"] == "efficacy" and r["basis"] == "claimed" for r in payload["rows"])


def test_never_prints_a_verdict_word_about_the_artifact(tmp_path, capsys):
    """The CLI reports well-formed/bound facts, never says the artifact 'passed' or is 'good'."""
    path = _write_statement(tmp_path, EXAMPLE)
    main(["verify", str(path)])
    out = capsys.readouterr().out.lower()
    for banned in ("artifact passed", "artifact is good", "artifact failed"):
        assert banned not in out
