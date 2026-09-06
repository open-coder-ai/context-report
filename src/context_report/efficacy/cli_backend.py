"""Backend that drives the `claude` CLI headlessly — measures the agent you actually use."""

from __future__ import annotations

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
    """Ask the local `claude` CLI one prompt in headless mode."""

    def __init__(self, timeout: int = _TIMEOUT) -> None:
        self.timeout = timeout

    def ask(self, prompt: str) -> str:
        executable = shutil.which(_CLI)
        if executable is None:
            raise RuntimeError(_NOT_ON_PATH)
        proc = subprocess.run(  # noqa: S603 - fixed argv, resolved path, prompt is not a shell string
            [executable, "-p", prompt],
            capture_output=True,
            text=True,
            timeout=self.timeout,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                _EXITED.format(cli=_CLI, code=proc.returncode, stderr=proc.stderr.strip()[:200])
            )
        return proc.stdout.strip()
