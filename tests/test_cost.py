"""Tests for the cost.* producer: latency, context tokens, and injected-text-path enumeration."""

from __future__ import annotations

import re
import sys

import pytest

from context_report import rows
from context_report.produce.cost import (
    context_tokens_row,
    injected_text_paths,
    latency_rows,
    pretooluse_payload,
)
from context_report.statement import Producer, Target, digest_path, statement, validate

NOOP_CMD = f'{sys.executable} -c "import sys; sys.stdin.read(); sys.exit(0)"'
SLEEP_CMD = f'{sys.executable} -c "import time; time.sleep(5)"'
BAD_CMD = "definitely-not-a-real-command-xyz"


def test_latency_rows_passes_and_validates(tmp_path):
    row = latency_rows(NOOP_CMD, pretooluse_payload(), n=5)
    assert row.result == rows.PASSED
    assert row.measurement.n == 5
    assert row.measurement.unit == "ms"
    assert row.environment_sensitive is True
    assert row.values["exit_codes"] == [0]

    (tmp_path / "hook.sh").write_text("#!/bin/sh\nexit 0\n")
    stmt = statement(
        subject_name="hook",
        subject_sha256=digest_path(tmp_path),
        subject_kind="hook",
        target=Target("claude_code"),
        producer=Producer("https://example.com/wf@v1"),
        rows=[row],
    )
    assert validate(stmt) == []


def test_latency_rows_reports_command_that_cannot_start(tmp_path):
    # With shell=True, subprocess.run itself refuses to even attempt the run for things the
    # shell can't do anything about, e.g. a cwd that doesn't exist -- that's an OSError before
    # any process exists. This is distinct from the shell running and reporting "not found" as
    # exit 127 (see test_latency_rows_reports_command_never_started below).
    missing_cwd = str(tmp_path / "does-not-exist")
    row = latency_rows(NOOP_CMD, pretooluse_payload(), n=3, cwd=missing_cwd)
    assert row.result == rows.ERROR
    assert row.reasoning


def test_latency_rows_reports_command_never_started():
    # cost.latency_ms measures the hook's latency. If every run exits 127 (shell "not found"),
    # the hook never ran, so a PASSED measurement here would be timing the shell's failure, not
    # the hook -- exactly the misleading number this format exists to prevent.
    row = latency_rows(BAD_CMD, pretooluse_payload(), n=3)
    assert row.result == rows.ERROR
    assert "never started" in row.reasoning
    assert "127" in row.reasoning


def test_latency_rows_mixed_exit_codes_stays_passed(tmp_path):
    # A command that sometimes exits 127 and sometimes 0 is a real, if strange, measurement --
    # not a "never started" case -- so it stays PASSED with both codes recorded.
    marker = tmp_path / "seen"
    script = (
        "import sys, pathlib; "
        f"p = pathlib.Path({str(marker)!r}); "
        "code = 0 if p.exists() else 127; "
        "p.touch(); "
        "sys.stdin.read(); "
        "sys.exit(code)"
    )
    cmd = f'{sys.executable} -c "{script}"'
    row = latency_rows(cmd, pretooluse_payload(), n=3)
    assert row.result == rows.PASSED
    assert row.values["exit_codes"] == [0, 127]


def test_latency_rows_that_never_exit_zero_is_an_error_with_numbers_kept():
    # A script the shell finds but python cannot open exits 2 on every run: the hook never made
    # a decision, so the timing is of the failure path. Found in the first dogfood, where an
    # unresolved plugin-root variable produced a confident 16 ms "latency".
    cmd = f'{sys.executable} -c "import sys; sys.stdin.read(); sys.exit(2)"'
    row = latency_rows(cmd, pretooluse_payload(), n=3)
    assert row.result == rows.ERROR
    assert "no run exited 0" in row.reasoning and "[2]" in row.reasoning
    assert row.measurement.n == 3, "the numbers stay for inspection; the result does not vouch"
    assert row.values["exit_codes"] == [2]


def test_latency_rows_reports_timeout():
    row = latency_rows(SLEEP_CMD, pretooluse_payload(), n=3, timeout_s=0.5)
    assert row.result == rows.ERROR
    assert row.reasoning


def _independent_token_count(text: str) -> int:
    return len(re.findall(r"\w+|[^\w\s]", text))


def test_context_tokens_row_matches_independent_count(tmp_path):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("Hello, world! This is a test.")
    b.write_text("Another file: with punctuation, and words.")

    row = context_tokens_row([a, b])
    expected = _independent_token_count(a.read_text()) + _independent_token_count(b.read_text())

    assert row.result == rows.PASSED
    assert row.measurement.mean == expected
    assert row.measurement.min == expected
    assert row.measurement.max == expected
    assert row.measurement.n == 1
    assert set(row.values["per_file"]) == {str(a), str(b)}
    assert row.values["per_file"][str(a)] == _independent_token_count(a.read_text())
    assert row.values["per_file"][str(b)] == _independent_token_count(b.read_text())


def test_context_tokens_row_input_hash_changes_on_byte_change(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("hello world")
    first = context_tokens_row([f]).input_hash

    again = context_tokens_row([f]).input_hash
    assert again == first

    f.write_text("hello world!")
    changed = context_tokens_row([f]).input_hash
    assert changed != first


def test_context_tokens_row_skips_binary_and_lists_it(tmp_path):
    text_file = tmp_path / "ok.txt"
    text_file.write_text("some words here")
    binary_file = tmp_path / "bad.bin"
    binary_file.write_bytes(b"\xff\xfe\x00\x01\x80\x81")

    row = context_tokens_row([text_file, binary_file])
    assert row.result == rows.PASSED
    assert str(binary_file) in row.values["skipped"]
    assert str(text_file) in row.values["per_file"]


def test_context_tokens_row_empty_dir_is_not_applicable():
    row = context_tokens_row([])
    assert row.result == rows.NOT_APPLICABLE
    assert row.reasoning == "no text files to count"


def test_injected_text_paths_instruction_file(tmp_path):
    f = tmp_path / "AGENTS.md"
    f.write_text("instructions")
    assert injected_text_paths(f, "instruction-file") == [f]


def test_injected_text_paths_subagent(tmp_path):
    f = tmp_path / "reviewer.md"
    f.write_text("subagent")
    assert injected_text_paths(f, "subagent") == [f]


def test_injected_text_paths_hook_is_empty(tmp_path):
    f = tmp_path / "pre_tool_use.py"
    f.write_text("print('hook')")
    assert injected_text_paths(f, "hook") == []


def test_injected_text_paths_skill(tmp_path):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("skill")
    extra = skill_dir / "REFERENCE.md"
    extra.write_text("reference")
    (skill_dir / "script.py").write_text("print(1)")

    result = injected_text_paths(skill_dir, "skill")
    assert result == [skill_md, extra]


def test_injected_text_paths_mcp_server(tmp_path):
    server_dir = tmp_path / "server"
    server_dir.mkdir()
    manifest = server_dir / "tools.json"
    manifest.write_text("{}")
    (server_dir / "sub").mkdir()
    (server_dir / "sub" / "nested.json").write_text("{}")

    assert injected_text_paths(server_dir, "mcp-server") == [manifest]


def test_injected_text_paths_plugin(tmp_path):
    plugin_dir = tmp_path / "plugin"
    (plugin_dir / "skills" / "a").mkdir(parents=True)
    (plugin_dir / "skills" / "a" / "SKILL.md").write_text("a")
    (plugin_dir / "skills" / "b").mkdir(parents=True)
    (plugin_dir / "skills" / "b" / "SKILL.md").write_text("b")
    (plugin_dir / "rules" / "nested").mkdir(parents=True)
    (plugin_dir / "rules" / "top.md").write_text("top rule")
    (plugin_dir / "rules" / "nested" / "deep.md").write_text("deep rule")
    (plugin_dir / "hooks").mkdir()
    (plugin_dir / "hooks" / "hooks.json").write_text("{}")

    result = injected_text_paths(plugin_dir, "plugin")
    assert plugin_dir / "skills" / "a" / "SKILL.md" in result
    assert plugin_dir / "skills" / "b" / "SKILL.md" in result
    assert plugin_dir / "rules" / "top.md" in result
    assert plugin_dir / "rules" / "nested" / "deep.md" in result
    assert plugin_dir / "hooks" / "hooks.json" in result
    assert len(result) == 5


def test_injected_text_paths_plugin_counts_the_copilot_hooks_file(tmp_path):
    """Copilot bundles keep hooks.json under com.github.copilot/; it must count like the others."""
    plugin_dir = tmp_path / "copilot-plugin"
    (plugin_dir / "skills" / "a").mkdir(parents=True)
    (plugin_dir / "skills" / "a" / "SKILL.md").write_text("a")
    hooks = plugin_dir / "com.github.copilot" / "hooks" / "hooks.json"
    hooks.parent.mkdir(parents=True)
    hooks.write_text("{}")

    result = injected_text_paths(plugin_dir, "plugin")
    assert hooks in result and len(result) == 2


def test_injected_text_paths_plugin_without_hooks_json(tmp_path):
    plugin_dir = tmp_path / "plugin2"
    (plugin_dir / "skills").mkdir(parents=True)
    (plugin_dir / "rules").mkdir(parents=True)

    assert injected_text_paths(plugin_dir, "plugin") == []


def test_injected_text_paths_unknown_kind_raises(tmp_path):
    with pytest.raises(ValueError, match="gizmo"):
        injected_text_paths(tmp_path, "gizmo")
