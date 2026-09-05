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
) -> Row:
    """Run `command` n times, feeding it `payload` on stdin, and time each run in milliseconds.

    Each run is `subprocess.run(command, shell=True, input=json.dumps(payload), ...)`, timed
    wall-clock with `time.perf_counter`. A run that cannot start or that times out aborts the
    whole measurement -- there is no partial, silently-truncated result -- and is reported as an
    honest `not_measured` row instead of a fabricated number.
    """
    stdin_blob = json.dumps(payload)
    samples_ms: list[float] = []
    exit_codes: list[int] = []
    for _ in range(n):
        started = time.perf_counter()
        try:
            proc = subprocess.run(  # noqa: S602 -- shell=True is the point: real tool invocation
                command,
                shell=True,
                input=stdin_blob,
                capture_output=True,
                timeout=timeout_s,
                cwd=cwd,
                text=True,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return not_measured(
                "cost.latency_ms", ERROR, reasoning=str(exc), inputs=(command, payload, n)
            )
        samples_ms.append((time.perf_counter() - started) * 1000)
        exit_codes.append(proc.returncode)
    return Row(
        attribute="cost.latency_ms",
        basis=RE_DERIVABLE,
        result=PASSED,
        input_hash=input_hash("cost.latency_ms", command, payload, n),
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


def context_tokens_row(paths: list[str | Path], *, method: str = "approx-regex-v1") -> Row:
    """Sum an estimated token count over `paths`.

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
    ordered = sorted(str(p) for p in paths)
    for raw in ordered:
        file_path = Path(raw)
        try:
            data = file_path.read_bytes()
            text = data.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            skipped.append(raw)
            continue
        per_file[raw] = len(TOKEN_RE.findall(text))
        hashed.append((raw, hashlib.sha256(data).hexdigest()))

    if not per_file:
        return not_measured(
            "cost.context_tokens",
            NOT_APPLICABLE,
            reasoning="no text files to count",
            inputs=(ordered,),
        )

    total = sum(per_file.values())
    values: dict[str, object] = {"per_file": per_file}
    if skipped:
        values["skipped"] = skipped

    return Row(
        attribute="cost.context_tokens",
        basis=RE_DERIVABLE,
        result=PASSED,
        input_hash=input_hash("cost.context_tokens", hashed, method),
        measurement=Measurement(
            unit="tokens", n=1, mean=total, min=total, max=total, percentiles={}
        ),
        conditions={"tokenizer": method, "files": len(per_file)},
        values=values,
    )


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
        hooks_json = subject_path / "hooks" / "hooks.json"
        if hooks_json.exists():
            paths.append(hooks_json)
        return paths
    if subject_kind == "hook":
        return []
    if subject_kind == "mcp-server":
        return sorted(subject_path.glob("*.json"))
    if subject_kind == "subagent":
        return [subject_path]
    raise ValueError(f"unknown subject kind {subject_kind!r}")
