"""Discover a plugin bundle's own hooks, instead of asking the user to name a hook command."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any


def _table() -> dict[str, Any]:
    blob = files("context_report.data").joinpath("bundle-layout-v0.1.json").read_text("utf-8")
    return json.loads(blob)["targets"]


def known_layouts() -> dict[str, dict[str, Any]]:
    """Every target's bundle-layout facts, keyed by target id."""
    return dict(_table())


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


def _shell_word(arg: str) -> str:
    """Quote an arg so spaces survive but `${CLAUDE_PLUGIN_ROOT}` still expands: double quotes.

    `shlex.quote` uses single quotes, which would hand the shell the literal text
    `${CLAUDE_PLUGIN_ROOT}/hooks/x.sh`; the client substitutes that variable before running, and
    the shell only does so inside double quotes or bare words.
    """
    if re.fullmatch(r"[A-Za-z0-9_./:=@%+,${}-]+", arg):
        return arg
    escaped = arg.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`")
    return f'"{escaped}"'


def _command_of(hook: dict[str, Any]) -> str | None:
    """`command` plus any `args`, joined as the shell would receive them; None if no command."""
    command = hook.get("command")
    if not isinstance(command, str):
        return None
    args = hook.get("args")
    if isinstance(args, list) and args:
        return " ".join([command, *(_shell_word(str(a)) for a in args)])
    return command


def _commands_in_entry(entry: dict[str, Any]) -> list[str]:
    """A hooks.json entry: nested `{"hooks": [{"command": ...}]}` or flat `{"command": ...}`."""
    hooks = entry.get("hooks", [entry])
    out: list[str] = []
    for h in hooks:
        if isinstance(h, dict):
            command = _command_of(h)
            if command is not None:
                out.append(command)
    return out


def _hook_docs(subject_path: Path, info: dict[str, Any]) -> list[dict[str, Any]]:
    """Every hooks document the client would read: the layout's file, plus the manifest's."""
    root = Path(subject_path)
    sources: list[Path] = [root / info["hooks_file"]]
    inline: list[dict[str, Any]] = []
    manifest = info.get("manifest")
    if manifest and (root / manifest).is_file():
        try:
            declared = json.loads((root / manifest).read_text("utf-8")).get("hooks")
        except (OSError, json.JSONDecodeError):
            declared = None
        if isinstance(declared, str):
            sources.append(root / declared)
        elif isinstance(declared, list):
            sources.extend(root / p for p in declared if isinstance(p, str))
        elif isinstance(declared, dict):
            inline.append(declared)
    docs: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for path in sources:
        resolved = path.resolve()
        if resolved in seen or not path.is_file():
            continue
        seen.add(resolved)
        try:
            docs.append(json.loads(path.read_text("utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return docs + inline


def discover_hooks(subject_path: Path, target: str) -> list[Hook]:
    """Every hook `target`'s client would run for this plugin bundle, in file order.

    An unknown target, a missing hooks file, or a hooks file that fails to parse all yield an
    empty list -- discovery is best-effort, never a hard error, since v0.1 still has to emit a
    complete statement either way.
    """
    info = layout(target)
    if info is None:
        return []
    discovered: list[Hook] = []
    index_by_event: dict[str, int] = {}
    for doc in _hook_docs(subject_path, info):
        hooks = doc.get("hooks", doc) if isinstance(doc, dict) else {}
        for event, entries in hooks.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                for command in _commands_in_entry(entry):
                    index = index_by_event.get(event, 0)
                    discovered.append(Hook(event=event, index=index, command=command))
                    index_by_event[event] = index + 1
    return discovered


def plugin_root_env(target: str, subject_path: Path) -> dict[str, str]:
    """`{root_var: subject_path}` for a target with a known plugin-root variable; `{}` otherwise."""
    info = layout(target)
    if info is None:
        return {}
    return {info["root_var"]: str(subject_path)}
