"""Discover a plugin bundle's own hooks, instead of asking the user to name a hook command."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any


def _table() -> dict[str, Any]:
    blob = files("context_report.data").joinpath("bundle-layout-v0.1.json").read_text("utf-8")
    return json.loads(blob)["targets"]


def layout(target: str) -> dict[str, Any] | None:
    """The bundle-layout facts for `target` (hooks file, plugin-root var), or None if unknown."""
    return _table().get(target)


@dataclass(frozen=True)
class Hook:
    """One hook command declared in a plugin's hooks file, under one event."""

    event: str
    index: int
    command: str

    @property
    def hook_id(self) -> str:
        return f"{self.event}:{self.index}"


def _commands_in_entry(entry: dict[str, Any]) -> list[str]:
    """A hooks.json entry: nested `{"hooks": [{"command": ...}]}` or flat `{"command": ...}`."""
    if "hooks" in entry:
        return [h["command"] for h in entry["hooks"] if isinstance(h, dict) and "command" in h]
    if "command" in entry:
        return [entry["command"]]
    return []


def discover_hooks(subject_path: Path, target: str) -> list[Hook]:
    """Every hook `target`'s client would run for this plugin bundle, in file order.

    An unknown target, a missing hooks file, or a hooks file that fails to parse all yield an
    empty list -- discovery is best-effort, never a hard error, since v0.1 still has to emit a
    complete statement either way.
    """
    info = layout(target)
    if info is None:
        return []
    hooks_file = Path(subject_path) / info["hooks_file"]
    if not hooks_file.is_file():
        return []
    try:
        doc = json.loads(hooks_file.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    discovered: list[Hook] = []
    for event, entries in doc.get("hooks", {}).items():
        if not isinstance(entries, list):
            continue
        index = 0
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for command in _commands_in_entry(entry):
                discovered.append(Hook(event=event, index=index, command=command))
                index += 1
    return discovered


def plugin_root_env(target: str, subject_path: Path) -> dict[str, str]:
    """`{root_var: subject_path}` for a target with a known plugin-root variable; `{}` otherwise."""
    info = layout(target)
    if info is None:
        return {}
    return {info["root_var"]: str(subject_path)}
