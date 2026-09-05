"""`produce` emits a complete statement: every attribute has a row, and unmeasured ones say why."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from context_report.cli import main
from context_report.produce.run import EXEC_ATTRIBUTES, produce_statement
from context_report.rows import ATTRIBUTES, CLAIMED, NOT_APPLICABLE, NOT_AVAILABLE, PASSED
from context_report.statement import digest_path, validate

GATE = (
    "import sys, json\ndata = sys.stdin.read()\njson.loads(data) if data else None\nsys.exit(0)\n"
)


@pytest.fixture
def hook_dir(tmp_path: Path) -> Path:
    (tmp_path / ".hooks").mkdir()
    (tmp_path / ".hooks" / "gate.py").write_text(GATE)
    (tmp_path / "README.md").write_text("A hook that allows everything.\n")
    return tmp_path


def _rows(stmt: dict) -> dict[str, dict]:
    return {a["attribute"]: a for a in stmt["predicate"]["attributes"]}


def test_hook_subject_yields_every_attribute_and_validates(hook_dir: Path) -> None:
    cmd = f'python3 "{hook_dir}/.hooks/gate.py"'
    stmt = produce_statement(
        subject=hook_dir, subject_kind="hook", target="claude_code", hook_command=cmd, n=3
    )
    assert validate(stmt) == []
    rows = _rows(stmt)
    assert set(rows) == set(ATTRIBUTES), "every v0.1 attribute must have a row"
    assert rows["reachability"]["result"] == PASSED
    assert rows["cost.latency_ms"]["measurement"]["n"] == 3
    assert rows["fault.malformedOutput"]["result"] == PASSED
    for attr in ("fault.scriptMissing", "fault.interpreterMissing", "fault.timeout"):
        assert rows[attr]["result"] == NOT_AVAILABLE
        assert "requires driving" in rows[attr]["reasoning"]
    # efficacy does not apply to a hook (attributes.md): NotApplicable, still claimed.
    assert rows["efficacy"]["basis"] == CLAIMED and rows["efficacy"]["result"] == NOT_APPLICABLE
    assert "does not apply to subjectKind hook" in rows["efficacy"]["reasoning"]
    assert rows["cost.context_tokens"]["result"] == NOT_APPLICABLE


def test_mcp_server_marks_decision_and_interference_not_applicable(tmp_path: Path) -> None:
    (tmp_path / "server.json").write_text('{"tools": [{"name": "t", "description": "does x"}]}')
    stmt = produce_statement(subject=tmp_path, subject_kind="mcp-server", target="claude_code")
    assert validate(stmt) == []
    rows = _rows(stmt)
    for attr in ("decision", "interference"):
        assert rows[attr]["result"] == NOT_APPLICABLE
        assert "does not apply to subjectKind mcp-server" in rows[attr]["reasoning"]
    assert rows["efficacy"]["result"] == NOT_AVAILABLE, "efficacy still applies to an mcp-server"


def test_input_hashes_are_bound_to_subject_and_target(tmp_path: Path) -> None:
    """Two statements about different bundles, or different targets, never share an inputHash."""
    a, b = tmp_path / "a", tmp_path / "b"
    for d, text in ((a, "- Rule one.\n"), (b, "- Rule two.\n")):
        d.mkdir()
        (d / "AGENTS.md").write_text(text)

    def hashes(subject: Path, target: str) -> dict[str, str]:
        stmt = produce_statement(subject=subject, subject_kind="instruction-file", target=target)
        return {
            r["attribute"]: r["inputHash"]
            for r in stmt["predicate"]["attributes"]
            if "inputHash" in r
        }

    same = hashes(a, "devin")
    assert same == hashes(a, "devin"), "the convention is deterministic"
    other_subject, other_target = hashes(b, "devin"), hashes(a, "cursor")
    for attr, h in same.items():
        assert other_subject[attr] != h, f"{attr}: hash did not change with the subject"
        assert other_target[attr] != h, f"{attr}: hash did not change with the target"


def test_env_is_recorded_on_the_rows_that_ran_under_it(hook_dir: Path) -> None:
    cmd = 'python3 "$MY_ROOT/.hooks/gate.py"'
    stmt = produce_statement(
        subject=hook_dir,
        subject_kind="hook",
        target="cursor",
        hook_command=cmd,
        env={"MY_ROOT": str(hook_dir)},
        n=2,
    )
    rows = _rows(stmt)
    assert rows["reachability"]["result"] == PASSED, "the variable made the script reachable"
    assert rows["reachability"]["environment"]["env"] == {"MY_ROOT": str(hook_dir)}
    assert rows["cost.latency_ms"]["environment"]["env"] == {"MY_ROOT": str(hook_dir)}


def test_instruction_file_marks_executable_rows_not_applicable(tmp_path: Path) -> None:
    agents = tmp_path / "AGENTS.md"
    agents.write_text("- Never commit secrets.\n- Run the tests before pushing.\n")
    stmt = produce_statement(subject=agents, subject_kind="instruction-file", target="devin")
    assert validate(stmt) == []
    rows = _rows(stmt)
    for attr in EXEC_ATTRIBUTES:
        assert rows[attr]["result"] == NOT_APPLICABLE
        assert "nothing to execute" in rows[attr]["reasoning"]
    assert rows["cost.context_tokens"]["result"] == PASSED
    assert rows["cost.context_tokens"]["measurement"]["mean"] > 0


def test_plugin_without_hook_command_says_so(tmp_path: Path) -> None:
    (tmp_path / "skills" / "s").mkdir(parents=True)
    (tmp_path / "skills" / "s" / "SKILL.md").write_text("# skill\nDo the thing.\n")
    stmt = produce_statement(subject=tmp_path, subject_kind="plugin", target="copilot")
    rows = _rows(stmt)
    assert rows["reachability"]["result"] == NOT_APPLICABLE
    assert "no hook command" in rows["reachability"]["reasoning"]
    assert rows["cost.context_tokens"]["result"] == PASSED


def test_statement_records_configuration_digest_and_producer(hook_dir: Path) -> None:
    stmt = produce_statement(
        subject=hook_dir, subject_kind="hook", target="claude_code", producer_id="https://p/x@v1"
    )
    assert stmt["predicate"]["producer"]["id"] == "https://p/x@v1"
    assert stmt["predicate"]["configuration"][0]["name"] == "produce-args"
    assert stmt["predicate"]["metadata"]["startedOn"].endswith("Z")


def test_cli_produce_then_verify_roundtrip(hook_dir: Path, tmp_path_factory) -> None:
    out = tmp_path_factory.mktemp("reports") / "stmt.json"  # outside the subject, deliberately
    cmd = f'python3 "{hook_dir}/.hooks/gate.py"'
    rc = main(
        [
            "produce",
            "--subject",
            str(hook_dir),
            "--kind",
            "hook",
            "--target",
            "claude_code",
            "--hook-command",
            cmd,
            "--n",
            "2",
            "--out",
            str(out),
        ]
    )
    assert rc == 0 and out.exists()
    stmt = json.loads(out.read_text())
    assert validate(stmt) == []
    assert main(["verify", str(out), "--subject", str(hook_dir)]) == 0


def test_cli_produce_usage_errors_exit_2(tmp_path: Path) -> None:
    assert main(["produce", "--kind", "hook", "--target", "x"]) == 2  # missing --subject
    assert (
        main(["produce", "--subject", str(tmp_path / "nope"), "--kind", "hook", "--target", "x"])
        == 2
    )
    assert (
        main(
            [
                "produce",
                "--subject",
                str(tmp_path),
                "--kind",
                "hook",
                "--target",
                "x",
                "--env",
                "BAD",
            ]
        )
        == 2
    )


def test_cli_refuses_to_write_the_report_inside_the_subject(hook_dir: Path) -> None:
    """Writing the report into the artifact changes the digest the report is bound to."""
    rc = main(
        [
            "produce",
            "--subject",
            str(hook_dir),
            "--kind",
            "hook",
            "--target",
            "x",
            "--out",
            str(hook_dir / "report.json"),
        ]
    )
    assert rc == 2 and not (hook_dir / "report.json").exists()


def test_producing_leaves_the_subject_byte_identical(hook_dir: Path) -> None:
    """Measuring must not alter the measured: the subject digest is the same before and after."""
    before = digest_path(hook_dir)
    cmd = f'python3 "{hook_dir}/.hooks/gate.py"'
    stmt = produce_statement(
        subject=hook_dir, subject_kind="hook", target="claude_code", hook_command=cmd, n=2
    )
    assert digest_path(hook_dir) == before
    assert stmt["subject"][0]["digest"]["sha256"] == before


def test_env_does_not_leak_between_runs(hook_dir: Path) -> None:
    """The resolved run must not make the unresolved run reachable. Found in the first dogfood."""
    cmd = 'python3 "$LEAK_ROOT/.hooks/gate.py"'
    assert "LEAK_ROOT" not in os.environ
    resolved = produce_statement(
        subject=hook_dir,
        subject_kind="hook",
        target="cursor",
        hook_command=cmd,
        env={"LEAK_ROOT": str(hook_dir)},
        n=2,
    )
    assert "LEAK_ROOT" not in os.environ, "produce_statement leaked its --env into the process"
    unresolved = produce_statement(
        subject=hook_dir, subject_kind="hook", target="cursor", hook_command=cmd, n=2
    )
    assert _rows(resolved)["reachability"]["result"] == PASSED
    assert _rows(unresolved)["reachability"]["result"] != PASSED
