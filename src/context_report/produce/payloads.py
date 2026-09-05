"""Realistic per-target hook payloads, and how to read a deny out of a hook's stdout."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

GENERIC = "generic"


def _table() -> dict[str, Any]:
    blob = files("context_report.data").joinpath("payloads-v0.1.json").read_text("utf-8")
    return json.loads(blob)["targets"]


def known_targets() -> tuple[str, ...]:
    return tuple(sorted(_table()))


def shape(target: str) -> dict[str, Any] | None:
    """The recorded payload shape for `target`, or None when we have no verified facts for it."""
    return _table().get(target)


def _set_path(obj: dict[str, Any], path: list[str], value: Any) -> None:
    cur = obj
    for key in path[:-1]:
        cur = cur.setdefault(key, {})
    cur[path[-1]] = value


def pre_tool_payload(target: str, command: str, *, cwd: str = "/") -> tuple[dict[str, Any], dict]:
    """A payload the target's adapter will treat as a real shell pre-tool event.

    Returns (payload, provenance). Provenance names the shape and its evidence basis so a row
    can record what it was probed with; an unknown target gets the generic two-key payload and
    provenance saying so -- a consumer must know the measurement may have hit an early exit.
    """
    s = shape(target)
    if s is None:
        payload = {"tool_name": "Bash", "tool_input": {"command": command}}
        return payload, {"shape": GENERIC, "basis": "none", "target": target}
    payload: dict[str, Any] = {s["event_key"]: s["event_name"]}
    if s["tool_key"]:
        payload[s["tool_key"]] = s["tool_value"]
    _set_path(payload, list(s["command_path"]), command)
    payload[s["cwd_key"]] = cwd
    payload[s["session_key"]] = "context-report"
    return payload, {"shape": f"{target}/{s['event_name']}/v0.1", "basis": s["basis"]}


def _get_path(obj: Any, path: list[str]) -> Any:
    for key in path:
        if not isinstance(obj, dict) or key not in obj:
            return None
        obj = obj[key]
    return obj


def stdout_decision(target: str, stdout: str) -> str | None:
    """The decision word a hook wrote to stdout, if any -- e.g. 'deny', 'block', 'ask', 'allow'."""
    text = stdout.strip()
    if not text:
        return None
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        # Some adapters print a human line before the JSON; try the last line.
        try:
            doc = json.loads(text.splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            return None
    s = shape(target)
    paths = (
        s["deny_paths"]
        if s
        else [["hookSpecificOutput", "permissionDecision"], ["decision"], ["permission"]]
    )
    for path in paths:
        val = _get_path(doc, path)
        if isinstance(val, str):
            return val.lower()
    return None


def is_deny(target: str, decision: str | None) -> bool:
    """Whether a stdout decision word means the action would NOT proceed as requested."""
    if decision is None:
        return False
    s = shape(target)
    words = s["deny_words"] if s else ["deny", "block", "ask"]
    return decision in words
