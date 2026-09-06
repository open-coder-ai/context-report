"""Every GitHub Actions `uses:` in every workflow is pinned to a full commit SHA."""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / ".github" / "workflows"
USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)")
SHA_RE = re.compile(r"^[^@]+@[0-9a-f]{40}$")


def _workflow_files() -> list[Path]:
    return sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(WORKFLOWS_DIR.glob("*.yaml"))


def test_workflows_directory_is_not_empty() -> None:
    assert _workflow_files(), f"no workflow files found under {WORKFLOWS_DIR}"


def test_every_uses_is_sha_pinned() -> None:
    offenders = []
    for path in _workflow_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = USES_RE.match(line)
            if not match:
                continue
            ref = match.group(1)
            if not SHA_RE.match(ref):
                offenders.append(f"{path.relative_to(WORKFLOWS_DIR.parent.parent)}:{lineno}: {ref}")
    assert not offenders, "unpinned action reference(s):\n" + "\n".join(offenders)
