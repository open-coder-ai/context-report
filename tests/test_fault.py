"""Fault: what a guard script does on bad input is measurable; what a client does is not."""

from __future__ import annotations

from pathlib import Path

from context_report import rows
from context_report.produce.fault import (
    DOCUMENTED_FAULT_BEHAVIOUR,
    client_dependent_rows,
    malformed_output_row,
)
from context_report.statement import Producer, Target, digest_path, statement, validate

_ALLOW_ON_ERROR = (
    "import json, sys\n"
    "raw = sys.stdin.read()\n"
    "try:\n"
    "    obj = json.loads(raw)\n"
    "    if not isinstance(obj, dict) or obj.get('tool_input') is None:\n"
    "        raise ValueError('bad')\n"
    "except Exception:\n"
    "    sys.exit(0)\n"
    "sys.exit(0)\n"
)

_DENY_ON_ERROR = _ALLOW_ON_ERROR.replace("sys.exit(0)\nsys.exit(0)", "sys.exit(2)\nsys.exit(0)")


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


def test_malformed_output_records_exit_0_as_fail_open(tmp_path: Path) -> None:
    script = tmp_path / "gate.py"
    script.write_text(_ALLOW_ON_ERROR)
    command = f"python3 {script}"

    row = malformed_output_row(command, tmp_path)

    assert row.result == rows.PASSED  # PASSED means measured, not that the guard behaved well
    assert row.basis == rows.RE_DERIVABLE
    for case in ("on_malformed_json", "on_empty_stdin", "on_null_tool_input"):
        assert row.values[case]["exit"] == 0
        assert row.values[case]["would_allow_if_exit0_means_allow"] is True
    assert "fails open" in row.reasoning
    assert _validated(row, tmp_path) == []


def test_malformed_output_records_exit_2_as_fail_closed(tmp_path: Path) -> None:
    script = tmp_path / "gate.py"
    script.write_text(_DENY_ON_ERROR)
    command = f"python3 {script}"

    row = malformed_output_row(command, tmp_path)

    assert row.result == rows.PASSED
    for case in ("on_malformed_json", "on_empty_stdin", "on_null_tool_input"):
        assert row.values[case]["exit"] == 2
        assert row.values[case]["would_allow_if_exit0_means_allow"] is False
    assert _validated(row, tmp_path) == []


def test_input_hash_is_stable_and_command_sensitive(tmp_path: Path) -> None:
    script = tmp_path / "gate.py"
    script.write_text(_ALLOW_ON_ERROR)
    command = f"python3 {script}"

    first = malformed_output_row(command, tmp_path)
    second = malformed_output_row(command, tmp_path)
    assert first.input_hash == second.input_hash
    assert first.input_hash != malformed_output_row(command + " --strict", tmp_path).input_hash


def test_client_dependent_rows_are_not_available_by_design() -> None:
    """These are never a measurement; pinned so nobody upgrades them to one by accident."""
    result_rows = client_dependent_rows("copilot")

    assert [r.attribute for r in result_rows] == [
        "fault.scriptMissing",
        "fault.interpreterMissing",
        "fault.timeout",
    ]
    for row in result_rows:
        assert row.result == rows.NOT_AVAILABLE
        assert row.reasoning is not None
        assert "always fail-open" in row.reasoning
        assert "requires driving that client" in row.reasoning
        stmt = statement(
            subject_name="hook",
            subject_sha256="0" * 64,
            subject_kind="hook",
            target=Target("copilot"),
            producer=Producer("https://example.com/w4@v1"),
            rows=[row],
        )
        assert validate(stmt) == []


def test_client_dependent_rows_cover_every_documented_target() -> None:
    for target in ("claude_code", "copilot", "cursor"):
        result_rows = client_dependent_rows(target)
        assert len(result_rows) == 3
        for row in result_rows:
            assert row.result == rows.NOT_AVAILABLE
            assert DOCUMENTED_FAULT_BEHAVIOUR[target] in row.reasoning


def test_unknown_target_says_no_oracle_on_file() -> None:
    result_rows = client_dependent_rows("some_future_agent")
    for row in result_rows:
        assert row.result == rows.NOT_AVAILABLE
        assert "no documented oracle on file" in row.reasoning.lower()
