"""discover.py: read a plugin bundle's own hooks.json instead of asking the user for a command."""

from __future__ import annotations

import json
from pathlib import Path

from context_report.produce.discover import Hook, discover_hooks, layout, plugin_root_env


def test_layout_known_targets() -> None:
    assert layout("claude_code") == {
        "hooks_file": "hooks/hooks.json",
        "root_var": "CLAUDE_PLUGIN_ROOT",
        "basis": "chock-bundle-observed",
        "manifest": ".claude-plugin/plugin.json",
    }
    assert layout("cursor")["root_var"] == "CURSOR_PLUGIN_ROOT"
    assert layout("copilot")["hooks_file"] == "com.github.copilot/hooks/hooks.json"
    assert layout("codex_cli")["root_var"] == "PLUGIN_ROOT"


def test_layout_unknown_target_is_none() -> None:
    assert layout("some_future_agent") is None


def test_hook_id_combines_event_and_index() -> None:
    h = Hook(event="PreToolUse", index=3, command="true")
    assert h.hook_id == "PreToolUse:3"


def test_discover_hooks_nested_claude_style(tmp_path: Path) -> None:
    """`{"matcher":..., "hooks": [{"type": "command", "command": ...}]}`, claude/codex/copilot."""
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    doc = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "cmd-a"}]},
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "cmd-b"}]},
            ],
            "SessionStart": [{"hooks": [{"type": "command", "command": "cmd-c"}]}],
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(doc))

    hooks = discover_hooks(tmp_path, "claude_code")

    assert [h.hook_id for h in hooks] == ["PreToolUse:0", "PreToolUse:1", "SessionStart:0"]
    assert [h.command for h in hooks] == ["cmd-a", "cmd-b", "cmd-c"]


def test_discover_hooks_flat_cursor_style(tmp_path: Path) -> None:
    """Cursor's entries are flat: `{"command": ...}`, no nested "hooks" list."""
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    doc = {"hooks": {"beforeShellExecution": [{"command": "cmd-a"}, {"command": "cmd-b"}]}}
    (hooks_dir / "hooks.json").write_text(json.dumps(doc))

    hooks = discover_hooks(tmp_path, "cursor")

    assert [h.hook_id for h in hooks] == ["beforeShellExecution:0", "beforeShellExecution:1"]


def test_discover_hooks_copilot_nested_path(tmp_path: Path) -> None:
    """Copilot's hooks file lives under `com.github.copilot/hooks/`, not `hooks/`."""
    hooks_dir = tmp_path / "com.github.copilot" / "hooks"
    hooks_dir.mkdir(parents=True)
    doc = {"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "cmd-a"}]}]}}
    (hooks_dir / "hooks.json").write_text(json.dumps(doc))

    hooks = discover_hooks(tmp_path, "copilot")

    assert [h.command for h in hooks] == ["cmd-a"]
    # the wrong (claude-shaped) location must not be picked up
    assert discover_hooks(tmp_path, "claude_code") == []


def test_discover_hooks_multiple_commands_in_one_entry(tmp_path: Path) -> None:
    """A single matcher entry MAY list more than one command hook; each is its own hook."""
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    doc = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {"type": "command", "command": "cmd-a"},
                        {"type": "command", "command": "cmd-b"},
                    ],
                }
            ]
        }
    }
    (hooks_dir / "hooks.json").write_text(json.dumps(doc))

    hooks = discover_hooks(tmp_path, "claude_code")

    assert [h.hook_id for h in hooks] == ["PreToolUse:0", "PreToolUse:1"]


def test_discover_hooks_unknown_target_is_empty(tmp_path: Path) -> None:
    (tmp_path / "hooks").mkdir()
    (tmp_path / "hooks" / "hooks.json").write_text('{"hooks": {}}')
    assert discover_hooks(tmp_path, "some_future_agent") == []


def test_discover_hooks_missing_file_is_empty(tmp_path: Path) -> None:
    assert discover_hooks(tmp_path, "claude_code") == []


def test_discover_hooks_malformed_json_is_empty(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "hooks.json").write_text("not json{")
    assert discover_hooks(tmp_path, "claude_code") == []


def test_discover_hooks_empty_hooks_object_is_empty(tmp_path: Path) -> None:
    hooks_dir = tmp_path / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "hooks.json").write_text("{}")
    assert discover_hooks(tmp_path, "claude_code") == []


def test_plugin_root_env_known_target(tmp_path: Path) -> None:
    assert plugin_root_env("claude_code", tmp_path) == {"CLAUDE_PLUGIN_ROOT": str(tmp_path)}
    assert plugin_root_env("codex_cli", tmp_path) == {"PLUGIN_ROOT": str(tmp_path)}
    assert plugin_root_env("copilot", tmp_path) == {"PLUGIN_ROOT": str(tmp_path)}
    assert plugin_root_env("cursor", tmp_path) == {"CURSOR_PLUGIN_ROOT": str(tmp_path)}


def test_plugin_root_env_unknown_target_is_empty(tmp_path: Path) -> None:
    assert plugin_root_env("some_future_agent", tmp_path) == {}


def _plugin(tmp_path: Path) -> Path:
    plugin = tmp_path / "p"
    (plugin / ".claude-plugin").mkdir(parents=True)
    return plugin


def test_manifest_hooks_field_names_a_hooks_file_at_another_path(tmp_path: Path) -> None:
    """aws-core keeps hooks.json under com.anthropic.claude-code/; plugin.json points at it."""
    plugin = _plugin(tmp_path)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "p", "hooks": "./com.anthropic.claude-code/hooks/hooks.json"})
    )
    other = plugin / "com.anthropic.claude-code" / "hooks"
    other.mkdir(parents=True)
    other.joinpath("hooks.json").write_text(
        json.dumps({"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "a"}]}]}})
    )
    assert [h.command for h in discover_hooks(plugin, "claude_code")] == ["a"]


def test_manifest_hooks_field_may_be_a_list_or_inline(tmp_path: Path) -> None:
    plugin = _plugin(tmp_path)
    (plugin / "hooks").mkdir()
    (plugin / "hooks" / "hooks.json").write_text(
        json.dumps({"hooks": {"PreToolUse": [{"command": "default"}]}})
    )
    (plugin / "hooks" / "claude-hooks.json").write_text(
        json.dumps({"hooks": {"PreToolUse": [{"command": "listed"}]}})
    )
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"hooks": ["./hooks/claude-hooks.json", "./hooks/hooks.json"]})
    )
    assert [h.command for h in discover_hooks(plugin, "claude_code")] == ["default", "listed"]
    assert [h.hook_id for h in discover_hooks(plugin, "claude_code")] == [
        "PreToolUse:0",
        "PreToolUse:1",
    ], "one index space per event across every hooks document"

    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"hooks": {"PreToolUse": [{"command": "inline"}]}})
    )
    assert [h.command for h in discover_hooks(plugin, "claude_code")] == ["default", "inline"]


def test_args_are_part_of_the_command(tmp_path: Path) -> None:
    """planning-with-files runs `sh` with the script in args; the producer must run the script."""
    plugin = _plugin(tmp_path)
    (plugin / "hooks").mkdir()
    (plugin / "hooks" / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "sh",
                                    "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/run.sh", "a b"],
                                }
                            ]
                        }
                    ]
                }
            }
        )
    )
    [hook] = discover_hooks(plugin, "claude_code")
    assert hook.command == "sh '${CLAUDE_PLUGIN_ROOT}/hooks/run.sh' 'a b'"
