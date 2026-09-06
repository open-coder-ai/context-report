"""Producer for the two rows nobody measures today: real latency and real context weight."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import time
from pathlib import Path

from context_report.produce.discover import known_layouts
from context_report.rows import (
    ERROR,
    NOT_APPLICABLE,
    PASSED,
    RE_DERIVABLE,
    Measurement,
    Row,
    input_hash,
    not_measured,
)

TOKEN_RE = re.compile(r"\w+|[^\w\s]")

# Shell exit codes meaning the command never actually ran: 127 is "not found", 126 is "found but
# not executable". If every run hits one of these, the hook was never invoked and there is
# nothing to time.
_NOT_EXECUTABLE = 126
_NOT_FOUND = 127
_NEVER_STARTED_CODES = frozenset({_NOT_EXECUTABLE, _NOT_FOUND})


def pretooluse_payload(tool: str = "Bash", command: str = "ls") -> dict:
    """A PreToolUse-shaped stdin payload: {"tool_name": ..., "tool_input": {"command": ...}}."""
    return {"tool_name": tool, "tool_input": {"command": command}}


def latency_rows(  # noqa: PLR0913 -- keyword-only; this is the measurement's whole configuration
    command: str,
    payload: dict,
    *,
    n: int = 50,
    timeout_s: float = 30.0,
    cwd: str | None = None,
    env_note: dict | None = None,
    binding: tuple[object, ...] = (),
) -> Row:
    """Run `command` n times, feeding it `payload` on stdin, and time each run in milliseconds.

    Each run is `subprocess.run(command, shell=True, input=json.dumps(payload), ...)`, timed
    wall-clock with `time.perf_counter`. A run that times out aborts the whole measurement --
    there is no partial, silently-truncated result -- and is reported as an honest `not_measured`
    row instead of a fabricated number.

    Error when the command never started (all runs 126/127, timeout, or bad cwd) and when no run
    exited 0 -- a benign payload should be allowed, so that timed the failure path. In the second
    case the numbers are kept for inspection; the result just does not vouch for them.
    """
    stdin_blob = json.dumps(payload)
    samples_ms: list[float] = []
    exit_codes: list[int] = []
    for _ in range(n):
        started = time.perf_counter()
        try:
            proc = subprocess.run(  # noqa: S602 -- the hook command, run as the client runs it
                command,
                shell=True,  # nosemgrep -- the registered hook command, as the client runs it
                input=stdin_blob,
                capture_output=True,
                timeout=timeout_s,
                cwd=cwd,
                text=True,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return not_measured(
                "cost.latency_ms",
                ERROR,
                reasoning=str(exc),
                inputs=(command, payload, n),
                binding=binding,
            )
        samples_ms.append((time.perf_counter() - started) * 1000)
        exit_codes.append(proc.returncode)

    codes_seen = sorted(set(exit_codes))
    if codes_seen and set(codes_seen) <= _NEVER_STARTED_CODES:
        if len(codes_seen) == 1:
            code = codes_seen[0]
            reason = "not found" if code == _NOT_FOUND else "not executable"
            detail = f"shell exit {code} ({reason})"
        else:
            detail = f"shell exits {codes_seen} (not found / not executable)"
        return not_measured(
            "cost.latency_ms",
            ERROR,
            reasoning=f"command never started: {detail} on all {n} runs; nothing to time",
            inputs=(command, payload, n),
            binding=binding,
        )

    # A benign payload should be allowed, i.e. exit 0. If no run did, the numbers time the
    # failure path (a missing script, a crashing interpreter), not the hook's decision path.
    never_succeeded = 0 not in exit_codes
    return Row(
        attribute="cost.latency_ms",
        basis=RE_DERIVABLE,
        result=ERROR if never_succeeded else PASSED,
        reasoning=(
            f"no run exited 0 with a benign payload (exit codes {codes_seen}); the timing is "
            "of the failure path, not the hook, and is kept only for inspection"
            if never_succeeded
            else None
        ),
        input_hash=input_hash(*binding, "cost.latency_ms", command, payload, n),
        environment_sensitive=True,
        environment={
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            **(env_note or {}),
        },
        measurement=Measurement.from_samples(samples_ms, "ms"),
        conditions={"n": n, "warmup_excluded": False, "shell": True},
        values={"exit_codes": sorted(set(exit_codes))},
    )


def context_tokens_row(
    paths: list[str | Path],
    *,
    root: Path | None = None,
    method: str = "approx-regex-v1",
    binding: tuple[object, ...] = (),
) -> Row:
    """Sum an estimated token count over `paths`, named relative to `root` (the subject).

    Names, not absolute paths, go into `values["per_file"]` and the `inputHash`, so the row
    recomputes to the same hash wherever the subject is checked out.

    `approx-regex-v1` is fully specified and deterministic: for each readable text file, tokens
    are the matches of `re.compile(r"\\w+|[^\\w\\s]")` against its decoded (utf-8) content -- each
    run of word characters is one token, and each remaining non-whitespace character (punctuation)
    is its own token. The row's total is the sum of per-file counts.

    A file that cannot be read as utf-8 text is skipped and listed under `values["skipped"]`
    rather than guessed at. If no file is readable, the row is `NotApplicable`.
    """
    per_file: dict[str, int] = {}
    skipped: list[str] = []
    hashed: list[tuple[str, str]] = []
    named = sorted((_subject_relative(Path(p), root), Path(p)) for p in paths)
    for name, file_path in named:
        try:
            data = file_path.read_bytes()
            text = data.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            skipped.append(name)
            continue
        per_file[name] = len(TOKEN_RE.findall(text))
        hashed.append((name, hashlib.sha256(data).hexdigest()))

    if not per_file:
        return not_measured(
            "cost.context_tokens",
            NOT_APPLICABLE,
            reasoning="no text files to count",
            inputs=([name for name, _ in named],),
            binding=binding,
        )

    total = sum(per_file.values())
    values: dict[str, object] = {"per_file": per_file}
    if skipped:
        values["skipped"] = skipped

    return Row(
        attribute="cost.context_tokens",
        basis=RE_DERIVABLE,
        result=PASSED,
        input_hash=input_hash(*binding, "cost.context_tokens", hashed, method),
        measurement=Measurement(
            unit="tokens", n=1, mean=total, min=total, max=total, percentiles={}
        ),
        conditions={"tokenizer": method, "files": len(per_file)},
        values=values,
    )


def _subject_relative(path: Path, root: Path | None) -> str:
    """`path` as a name relative to the subject root; a file subject is named by its basename."""
    if root is None:
        return path.name
    root = Path(root)
    base = root if root.is_dir() else root.parent
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.name


def injected_text_paths(subject_path: Path, subject_kind: str) -> list[Path]:
    """Which files an agent would actually load into context, for a subject of the given kind."""
    subject_path = Path(subject_path)
    if subject_kind == "instruction-file":
        return [subject_path]
    if subject_kind == "skill":
        others = sorted(p for p in subject_path.glob("*.md") if p.name != "SKILL.md")
        return [subject_path / "SKILL.md", *others]
    if subject_kind == "plugin":
        paths = sorted((subject_path / "skills").rglob("SKILL.md"))
        paths += sorted((subject_path / "rules").rglob("*.md"))
        # The hooks file sits where the target agent looks for it; Copilot's is not under hooks/.
        # A plugin is measured per target, but its declared triggers are the same text wherever
        # the bundle keeps them, so every known layout's file is counted once.
        for hooks_file in sorted({lay["hooks_file"] for lay in known_layouts().values()}):
            candidate = subject_path / hooks_file
            if candidate.exists() and candidate not in paths:
                paths.append(candidate)
        return paths
    if subject_kind == "hook":
        return []
    if subject_kind == "mcp-server":
        return sorted(subject_path.glob("*.json"))
    if subject_kind == "subagent":
        return [subject_path]
    raise ValueError(f"unknown subject kind {subject_kind!r}")
