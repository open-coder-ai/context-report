"""Backend that drives the `claude` CLI headlessly -- measures the agent you actually use."""

from __future__ import annotations

import json
import shutil
import subprocess

_CLI = "claude"
_TIMEOUT = 120
_NOT_ON_PATH = "the `claude` CLI is not on PATH"
_EXITED = "{cli} exited {code}: {stderr}"


def available() -> bool:
    """True if the `claude` CLI is on PATH."""
    return shutil.which(_CLI) is not None


class CliAsker:
    """Ask the local `claude` CLI one prompt in headless mode, optionally pinning the model.

    `model` is whatever the CLI accepts: an alias such as `opus`, `sonnet`, `fable`, or a full id.
    The JSON output format is requested so token usage and the exact model served are recorded;
    plain text is accepted as a fallback for CLI versions that do not emit it.
    """

    def __init__(self, model: str | None = None, timeout: int = _TIMEOUT) -> None:
        self.model = model
        self.timeout = timeout
        self.last_usage: dict[str, int] | None = None
        self.last_model: str | None = None

    def ask(self, prompt: str) -> str:
        executable = shutil.which(_CLI)
        if executable is None:
            raise RuntimeError(_NOT_ON_PATH)
        argv = [executable, "-p", prompt, "--output-format", "json"]
        if self.model:
            argv += ["--model", self.model]
        proc = subprocess.run(  # noqa: S603 - fixed argv, resolved path, prompt is not a shell string
            argv,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                _EXITED.format(cli=_CLI, code=proc.returncode, stderr=proc.stderr.strip()[:200])
            )
        return self._parse(proc.stdout)

    def _parse(self, stdout: str) -> str:
        try:
            doc = json.loads(stdout)
        except json.JSONDecodeError:
            return stdout.strip()
        if not isinstance(doc, dict) or "result" not in doc:
            return stdout.strip()
        usage = doc.get("usage") or {}
        if isinstance(usage, dict) and "input_tokens" in usage:
            self.last_usage = {
                "inputTokens": int(usage.get("input_tokens", 0)),
                "outputTokens": int(usage.get("output_tokens", 0)),
            }
        served = doc.get("modelUsage")
        if isinstance(served, dict) and served:
            self.last_model = next(iter(served))  # keyed by the exact model id that answered
        return str(doc["result"]).strip()
