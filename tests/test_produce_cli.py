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


@pytest.fixture
def plugin_dir(tmp_path: Path) -> Path:
    """A fake claude_code plugin bundle: two PreToolUse hooks and one SessionStart hook."""
    plugin = tmp_path / "plugin"
    scripts = plugin / "scripts"
    scripts.mkdir(parents=True)
    for name in ("one", "two", "session"):
        (scripts / f"{name}.py").write_text(GATE)
    hooks_dir = plugin / "hooks"
    hooks_dir.mkdir()
    hooks_json = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/one.py"',
                        }
                    ],
                },
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/two.py"',
                        }
                    ],
                },
            ],
            "SessionStart": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/session.py"',
                        }
                    ]
                }
            ],
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(hooks_json))
    return plugin


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


def test_plugin_without_hooks_says_so(tmp_path: Path) -> None:
    """A plugin with no hooks.json is self-describing too: there is simply nothing to discover."""
    (tmp_path / "skills" / "s").mkdir(parents=True)
    (tmp_path / "skills" / "s" / "SKILL.md").write_text("# skill\nDo the thing.\n")
    stmt = produce_statement(subject=tmp_path, subject_kind="plugin", target="copilot")
    rows = _rows(stmt)
    assert rows["reachability"]["result"] == NOT_APPLICABLE
    assert "the plugin declares no hooks" in rows["reachability"]["reasoning"]
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


def test_plugin_discovers_hooks_and_derives_plugin_root(plugin_dir: Path) -> None:
    """No --hook-command, no --env: the plugin's own hooks.json and root var carry the whole run."""
    stmt = produce_statement(subject=plugin_dir, subject_kind="plugin", target="claude_code", n=2)
    assert validate(stmt) == []
    rows = _rows(stmt)

    reach = rows["reachability"]
    assert reach["result"] == PASSED
    assert set(reach["values"]["perHook"]) == {"PreToolUse:0", "PreToolUse:1"}
    assert reach["environment"]["env"]["CLAUDE_PLUGIN_ROOT"] == str(plugin_dir)
    for hook_values in reach["values"]["perHook"].values():
        assert set(hook_values["reachable_from"]) == {"root", "nested", "parent", "outside"}
    assert reach["values"]["reachable_from"] == ["root", "nested", "parent", "outside"]
    assert reach["values"]["unreachable_from"] == []
    skipped = reach["values"]["skippedHooks"]
    assert [s["hook_id"] for s in skipped] == ["SessionStart:0"]
    assert skipped[0]["reason"] == "v0.1 measures pre-tool hooks only"

    fault = rows["fault.malformedOutput"]
    assert fault["result"] == PASSED
    assert set(fault["values"]["perHook"]) == {"PreToolUse:0", "PreToolUse:1"}
    assert fault["values"]["wouldAllowAny"] is True
    assert [s["hook_id"] for s in fault["values"]["skippedHooks"]] == ["SessionStart:0"]

    latency = rows["cost.latency_ms"]
    assert latency["result"] == PASSED
    assert set(latency["values"]["perHook"]) == {"PreToolUse:0", "PreToolUse:1"}
    per_hook_means = [h["mean"] for h in latency["values"]["perHook"].values()]
    assert latency["measurement"]["mean"] == pytest.approx(sum(per_hook_means))
    assert latency["measurement"]["n"] == 2
    assert latency["conditions"]["aggregation"] == "sum-across-hooks"
    assert [s["hook_id"] for s in latency["values"]["skippedHooks"]] == ["SessionStart:0"]


def test_plugin_input_hash_changes_when_a_hook_is_added(plugin_dir: Path) -> None:
    before = produce_statement(subject=plugin_dir, subject_kind="plugin", target="claude_code", n=2)
    before_hash = _rows(before)["reachability"]["inputHash"]

    hooks_path = plugin_dir / "hooks" / "hooks.json"
    doc = json.loads(hooks_path.read_text())
    doc["hooks"]["PreToolUse"].append(
        {
            "matcher": "Bash",
            "hooks": [
                {"type": "command", "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/one.py"'}
            ],
        }
    )
    hooks_path.write_text(json.dumps(doc))

    after = produce_statement(subject=plugin_dir, subject_kind="plugin", target="claude_code", n=2)
    after_hash = _rows(after)["reachability"]["inputHash"]
    assert after_hash != before_hash


def test_plugin_caller_env_overrides_discovered_root(plugin_dir: Path) -> None:
    """--env can still override the plugin-root value discovery would otherwise pass in."""
    other_root = plugin_dir.parent / "elsewhere"
    other_root.mkdir()
    (other_root / "scripts").symlink_to(plugin_dir / "scripts")
    stmt = produce_statement(
        subject=plugin_dir,
        subject_kind="plugin",
        target="claude_code",
        env={"CLAUDE_PLUGIN_ROOT": str(other_root)},
        n=2,
    )
    rows = _rows(stmt)
    assert rows["reachability"]["environment"]["env"]["CLAUDE_PLUGIN_ROOT"] == str(other_root)
    assert rows["reachability"]["result"] == PASSED


def test_plugin_single_hook_still_emits_perhook(tmp_path: Path) -> None:
    """Exactly one hook still gets the perHook shape, with one key, not a flattened single row."""
    plugin = tmp_path / "plugin"
    scripts = plugin / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "guard.py").write_text(GATE)
    hooks_dir = plugin / "hooks"
    hooks_dir.mkdir()
    hooks_json = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/guard.py"',
                        }
                    ],
                }
            ]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(hooks_json))

    stmt = produce_statement(subject=plugin, subject_kind="plugin", target="claude_code", n=2)
    rows = _rows(stmt)
    assert list(rows["reachability"]["values"]["perHook"]) == ["PreToolUse:0"]
    assert "skippedHooks" not in rows["reachability"]["values"]


def test_plugin_flat_hook_entry_is_discovered(tmp_path: Path) -> None:
    """Cursor's hooks.json uses a flat {"command": ...} entry, not claude/copilot's nested shape."""
    plugin = tmp_path / "plugin"
    scripts = plugin / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "guard.py").write_text(GATE)
    hooks_dir = plugin / "hooks"
    hooks_dir.mkdir()
    hooks_json = {
        "hooks": {
            "beforeShellExecution": [
                {"command": 'python3 "${CURSOR_PLUGIN_ROOT}/scripts/guard.py"'}
            ]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(hooks_json))

    stmt = produce_statement(subject=plugin, subject_kind="plugin", target="cursor", n=2)
    rows = _rows(stmt)
    assert rows["reachability"]["result"] == PASSED
    assert rows["reachability"]["environment"]["env"]["CURSOR_PLUGIN_ROOT"] == str(plugin)


def test_plugin_with_hooks_but_none_pre_tool_stays_not_applicable(tmp_path: Path) -> None:
    plugin = tmp_path / "plugin"
    hooks_dir = plugin / "hooks"
    hooks_dir.mkdir(parents=True)
    hooks_json = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "true"}]}]}}
    (hooks_dir / "hooks.json").write_text(json.dumps(hooks_json))

    stmt = produce_statement(subject=plugin, subject_kind="plugin", target="claude_code")
    rows = _rows(stmt)
    assert rows["reachability"]["result"] == NOT_APPLICABLE
    assert "none on claude_code's pre-tool event" in rows["reachability"]["reasoning"]


def test_cli_rejects_hook_command_with_plugin_kind(plugin_dir: Path, capsys) -> None:
    rc = main(
        [
            "produce",
            "--subject",
            str(plugin_dir),
            "--kind",
            "plugin",
            "--target",
            "claude_code",
            "--hook-command",
            "echo hi",
        ]
    )
    assert rc == 2
    assert "self-describing" in capsys.readouterr().err


def test_produce_statement_ignores_hook_command_for_a_plugin(plugin_dir: Path) -> None:
    """The CLI rejects --hook-command with --kind plugin; the library function just ignores it."""
    stmt = produce_statement(
        subject=plugin_dir,
        subject_kind="plugin",
        target="claude_code",
        hook_command="definitely-not-used",
        n=2,
    )
    rows = _rows(stmt)
    assert rows["reachability"]["result"] == PASSED
    assert "definitely-not-used" not in json.dumps(rows["reachability"])
