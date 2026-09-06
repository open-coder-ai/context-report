"""Reachability producer: does a registered hook command actually start from every cwd it must."""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from context_report.rows import ERROR, FAILED, PASSED, RE_DERIVABLE, Row, input_hash, not_measured

ATTRIBUTE = "reachability"

CWD_LABELS = ("root", "nested", "parent", "outside")

#: exit 127 is "command not found"; exit 2 with one of these stderr fragments is the
#: interpreter's own "can't find the script" message (CPython, Node, and POSIX sh all use one
#: of these phrasings). Any other exit means the process started and ran its own logic.
_NOT_FOUND_STDERR_FRAGMENTS = ("can't open file", "No such file or directory", "not found")

_SCRIPT_EXTENSIONS = (".py", ".sh", ".js", ".ts")
#: A token is anchored (not a bare relative path) if it starts with an absolute slash, a shell
#: variable/command-substitution sigil, or one of those sigils immediately inside a quote that a
#: hand-rolled tokenizer (unlike shlex) would leave in place.
_ANCHORED_PREFIXES = ("/", "$", '"$', "'$")

DEFAULT_PAYLOAD = {"tool_name": "Bash", "tool_input": {"command": "true"}}


_EXIT_COMMAND_NOT_FOUND = 127
_EXIT_ERROR = 2


def _is_unreachable(proc: subprocess.CompletedProcess[str]) -> bool:
    """True when the exit reflects the interpreter never finding the script, not the script."""
    if proc.returncode == _EXIT_COMMAND_NOT_FOUND:
        return True
    stderr = proc.stderr or ""
    return proc.returncode == _EXIT_ERROR and any(
        frag in stderr for frag in _NOT_FOUND_STDERR_FRAGMENTS
    )


def _first_stderr_line(proc: subprocess.CompletedProcess[str]) -> str:
    """First line of stderr, or empty string when there was none."""
    stderr = proc.stderr or ""
    return stderr.splitlines()[0] if stderr else ""


def _has_relative_script_path(command: str) -> bool:
    """Static check: does `command` name a script by a path shell expansion can't anchor?

    Tokenizes with shlex so a quoted command substitution like `"$(git rev-parse
    --show-toplevel)/x.py"` stays one token instead of splitting on its internal spaces.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    return any(
        token.endswith(_SCRIPT_EXTENSIONS) and not token.startswith(_ANCHORED_PREFIXES)
        for token in tokens
    )


def _find_or_make_nested_dir(artifact_root: Path) -> tuple[Path, str]:
    """An existing dir two levels inside artifact_root, else one created under a tmp subdir."""
    for level1 in sorted(p for p in artifact_root.iterdir() if p.is_dir() and p.name != ".git"):
        for level2 in sorted(p for p in level1.iterdir() if p.is_dir()):
            return level2, "existing"
    created = artifact_root / "_context_report_tmp" / "nested"
    created.mkdir(parents=True, exist_ok=True)
    return created, "created"


def reachability_row(
    command: str,
    artifact_root: Path,
    *,
    payload: dict[str, Any] | None = None,
    timeout_s: float = 10.0,
    binding: tuple[object, ...] = (),
) -> Row:
    """Run `command` as a hook from four cwds; PASSED only if it starts from every one of them."""
    artifact_root = Path(artifact_root)
    resolved_payload = payload if payload is not None else DEFAULT_PAYLOAD
    payload_json = json.dumps(resolved_payload)
    nested_dir, nested_dir_source = _find_or_make_nested_dir(artifact_root)
    try:
        return _measure(
            command=command,
            artifact_root=artifact_root,
            nested_dir=nested_dir,
            nested_dir_source=nested_dir_source,
            payload_json=payload_json,
            resolved_payload=resolved_payload,
            timeout_s=timeout_s,
            binding=binding,
        )
    finally:
        # A measurement must not alter the artifact it measures: remove what we created.
        if nested_dir_source == "created":
            shutil.rmtree(artifact_root / "_context_report_tmp", ignore_errors=True)


def _measure(  # noqa: PLR0913 -- the run loop, split out so cleanup is a single finally
    *,
    command: str,
    artifact_root: Path,
    nested_dir: Path,
    nested_dir_source: str,
    payload_json: str,
    resolved_payload: dict[str, Any],
    timeout_s: float,
    binding: tuple[object, ...] = (),
) -> Row:
    with tempfile.TemporaryDirectory(prefix="context-report-reachability-") as outside_dir:
        cwds = {
            "root": artifact_root,
            "nested": nested_dir,
            "parent": artifact_root.parent,
            "outside": Path(outside_dir),
        }
        reachable_from: list[str] = []
        unreachable_from: list[str] = []
        stderr_first_line: dict[str, str] = {}
        for label in CWD_LABELS:
            try:
                proc = subprocess.run(  # noqa: S602  # nosemgrep -- run as the client runs it
                    command,
                    shell=True,
                    input=payload_json,
                    capture_output=True,
                    timeout=timeout_s,
                    cwd=cwds[label],
                    text=True,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                return not_measured(
                    ATTRIBUTE,
                    ERROR,
                    f"running from cwd {label!r} raised {exc!r}",
                    inputs=(command, resolved_payload, list(CWD_LABELS)),
                    binding=binding,
                )
            stderr_first_line[label] = _first_stderr_line(proc)
            (unreachable_from if _is_unreachable(proc) else reachable_from).append(label)

    result = PASSED if not unreachable_from else FAILED
    return Row(
        attribute=ATTRIBUTE,
        basis=RE_DERIVABLE,
        result=result,
        input_hash=input_hash(*binding, ATTRIBUTE, command, resolved_payload, list(CWD_LABELS)),
        conditions={
            "cwdTested": list(CWD_LABELS),
            "command": command,
            "nested_dir_source": nested_dir_source,
        },
        values={
            "reachable_from": reachable_from,
            "unreachable_from": unreachable_from,
            "stderr_first_line": stderr_first_line,
            "relative_script_path": _has_relative_script_path(command),
        },
        evidence=(),
    )
