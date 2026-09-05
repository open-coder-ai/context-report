"""Reachability: a guard registered by a relative path is a guard you can cd out of."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from context_report import rows
from context_report.produce.reachability import reachability_row
from context_report.statement import Producer, Target, digest_path, statement, validate

_ALLOW_SCRIPT = "import sys\nsys.stdin.read()\nsys.exit(0)\n"


def _validated(row: rows.Row, artifact_root: Path) -> list[str]:
    stmt = statement(
        subject_name="hook",
        subject_sha256=digest_path(artifact_root),
        subject_kind="hook",
        target=Target("claude_code"),
        producer=Producer("https://example.com/w4@v1"),
        rows=[row],
    )
    return validate(stmt)


def test_absolute_path_is_reachable_from_every_cwd(tmp_path: Path) -> None:
    hooks_dir = tmp_path / ".hooks"
    hooks_dir.mkdir()
    script = hooks_dir / "gate.py"
    script.write_text(_ALLOW_SCRIPT)
    command = f"python3 {script}"

    row = reachability_row(command, tmp_path)

    assert row.result == rows.PASSED
    assert set(row.values["reachable_from"]) == {"root", "nested", "parent", "outside"}
    assert row.values["unreachable_from"] == []
    assert row.values["relative_script_path"] is False
    assert _validated(row, tmp_path) == []


def test_relative_registration_is_unreachable_off_the_repo_root(tmp_path: Path) -> None:
    """Reproduces the cwd-dependence defect: `python3 .hooks/gate.py` only resolves at root."""
    hooks_dir = tmp_path / ".hooks"
    hooks_dir.mkdir()
    (hooks_dir / "gate.py").write_text(_ALLOW_SCRIPT)
    command = "python3 .hooks/gate.py"

    row = reachability_row(command, tmp_path)

    assert row.result == rows.FAILED
    assert row.values["reachable_from"] == ["root"]
    assert set(row.values["unreachable_from"]) == {"nested", "parent", "outside"}
    assert row.values["relative_script_path"] is True
    for label in ("nested", "parent", "outside"):
        stderr = row.values["stderr_first_line"][label]
        assert "No such file or directory" in stderr or "can't open file" in stderr
    assert _validated(row, tmp_path) == []


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_command_substitution_anchored_to_repo_root_survives_cd(tmp_path: Path) -> None:
    """A guard resolved via `$(git rev-parse --show-toplevel)` is reachable anywhere IN the repo."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)  # noqa: S607 -- test fixture
    hooks_dir = tmp_path / ".hooks"
    hooks_dir.mkdir()
    (hooks_dir / "gate.py").write_text(_ALLOW_SCRIPT)
    command = 'python3 "$(git rev-parse --show-toplevel)/.hooks/gate.py"'

    row = reachability_row(command, tmp_path)

    assert row.result == rows.FAILED
    assert set(row.values["reachable_from"]) == {"root", "nested"}
    assert set(row.values["unreachable_from"]) == {"parent", "outside"}
    assert row.values["relative_script_path"] is False
    assert _validated(row, tmp_path) == []


def test_input_hash_ignores_cwd_paths_but_not_command(tmp_path: Path) -> None:
    (tmp_path / ".hooks").mkdir()
    (tmp_path / ".hooks" / "gate.py").write_text(_ALLOW_SCRIPT)
    other_root = tmp_path / "elsewhere"
    other_root.mkdir()
    (other_root / ".hooks").mkdir()
    (other_root / ".hooks" / "gate.py").write_text(_ALLOW_SCRIPT)
    command = f"python3 {tmp_path / '.hooks' / 'gate.py'}"

    same_command_other_root = reachability_row(command, other_root)
    assert reachability_row(command, tmp_path).input_hash == same_command_other_root.input_hash
    assert (
        reachability_row("python3 x.py", tmp_path).input_hash
        != reachability_row("python3 y.py", tmp_path).input_hash
    )


def test_timeout_is_reported_as_error_not_a_result(tmp_path: Path) -> None:
    (tmp_path / ".hooks").mkdir()
    script = tmp_path / ".hooks" / "sleeper.py"
    script.write_text("import time\ntime.sleep(2)\n")
    command = f"python3 {script}"

    row = reachability_row(command, tmp_path, timeout_s=0.2)

    assert row.result == rows.ERROR
    assert row.reasoning
    assert _validated(row, tmp_path) == []
