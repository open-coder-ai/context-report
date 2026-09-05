"""Payloads carry the event key adapters gate on, and stdout decisions are read, not guessed."""

from __future__ import annotations

import json

import pytest

from context_report.produce import payloads

KNOWN = ("claude_code", "codex_cli", "copilot", "cursor")


@pytest.mark.parametrize("target", KNOWN)
def test_known_targets_produce_event_keyed_payloads(target: str) -> None:
    payload, prov = payloads.pre_tool_payload(target, "true", cwd="/w")
    s = payloads.shape(target)
    assert payload[s["event_key"]] == s["event_name"], "without this key the adapter exits silently"
    cur = payload
    for key in s["command_path"]:
        cur = cur[key]
    assert cur == "true"
    assert prov["basis"] in {"live-run", "live-run-partial"}
    assert prov["shape"].startswith(target)


def test_claude_code_payload_matches_the_verified_shape() -> None:
    payload, prov = payloads.pre_tool_payload("claude_code", "ls", cwd="/repo")
    assert payload["hook_event_name"] == "PreToolUse"
    assert payload["tool_name"] == "Bash"
    assert payload["tool_input"]["command"] == "ls"
    assert payload["cwd"] == "/repo" and payload["session_id"]
    assert prov["basis"] == "live-run"


def test_unknown_target_gets_generic_payload_and_says_so() -> None:
    payload, prov = payloads.pre_tool_payload("some-agent", "ls")
    assert payload == {"tool_name": "Bash", "tool_input": {"command": "ls"}}
    assert prov == {"shape": "generic", "basis": "none", "target": "some-agent"}


def test_stdout_decision_reads_hook_json_deny() -> None:
    out = json.dumps(
        {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny"}}
    )
    assert payloads.stdout_decision("claude_code", out) == "deny"
    assert payloads.is_deny("claude_code", "deny") is True
    assert payloads.is_deny("claude_code", "allow") is False
    assert payloads.is_deny("claude_code", None) is False


def test_stdout_decision_tolerates_a_human_line_before_the_json() -> None:
    out = "BLOCKED: nope\n" + json.dumps({"decision": "block"})
    assert payloads.stdout_decision("claude_code", out) == "block"


def test_stdout_decision_is_none_for_silence_or_prose() -> None:
    assert payloads.stdout_decision("claude_code", "") is None
    assert payloads.stdout_decision("claude_code", "just words") is None


def test_cursor_uses_top_level_command_and_permission() -> None:
    payload, _ = payloads.pre_tool_payload("cursor", "rm -rf x", cwd="/w")
    assert payload["command"] == "rm -rf x" and payload["conversation_id"]
    assert payloads.stdout_decision("cursor", json.dumps({"permission": "deny"})) == "deny"
    assert payloads.is_deny("cursor", "ask") is True
