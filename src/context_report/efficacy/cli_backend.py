"""Backend that drives the `claude` CLI headlessly -- measures the agent you actually use."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

_CLI = "claude"
_TIMEOUT = 600  # one agentic answer can take minutes; a real hang still ends the run
_ATTEMPTS = 2  # a timed-out call is retried once before the run is given up
_NOT_ON_PATH = "the `claude` CLI is not on PATH"
_EXITED = "{cli} exited {code}: {stderr}"
_TIMED_OUT = "{cli} produced no answer within {seconds}s, {attempts} attempt(s)"


def available() -> bool:
    """True if the `claude` CLI is on PATH."""
    return shutil.which(_CLI) is not None


class CliAsker:
    """Ask the local `claude` CLI one prompt in headless mode, optionally pinning the model.

    `model` is whatever the CLI accepts: an alias such as `opus`, `sonnet`, `fable`, or a full id.
    The JSON output format is requested so token usage and the exact model served are recorded;
    plain text is accepted as a fallback for CLI versions that do not emit it.
    """

    def __init__(
        self, model: str | None = None, timeout: int = _TIMEOUT, cwd: Path | None = None
    ) -> None:
        self.model = model
        self.timeout = timeout
        self.cwd = cwd  # the directory the agent works in; None means the caller's
        self.last_usage: dict[str, int] | None = None
        self.last_model: str | None = None

    def ask(self, prompt: str) -> str:
        executable = shutil.which(_CLI)
        if executable is None:
            raise RuntimeError(_NOT_ON_PATH)
        argv = [executable, "-p", prompt, "--output-format", "json"]
        if self.model:
            argv += ["--model", self.model]
        proc = self._run(argv)
        if proc.returncode != 0:
            raise RuntimeError(
                _EXITED.format(cli=_CLI, code=proc.returncode, stderr=proc.stderr.strip()[:200])
            )
        return self._parse(proc.stdout)

    def _run(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        """Run the CLI once, retrying a single timeout; a second timeout ends the run."""
        for attempt in range(1, _ATTEMPTS + 1):
            try:
                return subprocess.run(  # noqa: S603 - fixed argv, resolved path, prompt is not a shell string
                    argv,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    check=False,
                    cwd=self.cwd,
                )
            except subprocess.TimeoutExpired as exc:
                if attempt == _ATTEMPTS:
                    raise RuntimeError(
                        _TIMED_OUT.format(cli=_CLI, seconds=self.timeout, attempts=attempt)
                    ) from exc
        raise AssertionError("unreachable")  # pragma: no cover

    def _parse(self, stdout: str) -> str:
        try:
            doc = json.loads(stdout)
        except json.JSONDecodeError:
            return stdout.strip()
        if not isinstance(doc, dict) or "result" not in doc:
            return stdout.strip()
        usage = doc.get("usage") or {}
        if isinstance(usage, dict) and "input_tokens" in usage:
            self.last_usage = usage_from_cli(usage)
        served = doc.get("modelUsage")
        if isinstance(served, dict) and served:
            self.last_model = answering_model(served)
        return str(doc["result"]).strip()


def usage_from_cli(usage: dict[str, Any]) -> dict[str, int]:
    """Tokens per call. `input_tokens` alone omits the cached prefix, which is most of the input."""
    uncached = int(usage.get("input_tokens", 0))
    created = int(usage.get("cache_creation_input_tokens", 0) or 0)
    read = int(usage.get("cache_read_input_tokens", 0) or 0)
    return {
        "inputTokens": uncached + created + read,
        "outputTokens": int(usage.get("output_tokens", 0)),
        "uncachedInputTokens": uncached,
        "cacheCreationInputTokens": created,
        "cacheReadInputTokens": read,
    }


def answering_model(served: dict[str, Any]) -> str:
    """`modelUsage` also lists the CLI's helper models; the subject model wrote the most output."""
    return max(served, key=lambda k: int((served[k] or {}).get("outputTokens", 0) or 0))
