"""tools/quickstart_block.py pulls the README's first fenced bash block, and only that one."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from quickstart_block import extract_quickstart_block


def test_extracts_the_bash_block_under_the_heading() -> None:
    markdown = """
## 30-second quickstart

```bash
echo one
echo two
```

```json
{"not": "this"}
```

## Next section
"""
    assert extract_quickstart_block(markdown) == "echo one\necho two\n"


def test_missing_heading_raises() -> None:
    with pytest.raises(ValueError, match="heading"):
        extract_quickstart_block("# nothing here")


def test_missing_bash_fence_raises() -> None:
    markdown = "## 30-second quickstart\n\nno code block here\n"
    with pytest.raises(ValueError, match="no closed fenced bash block"):
        extract_quickstart_block(markdown)


def test_a_broken_extracted_block_fails_under_bash_dash_e() -> None:
    """Proves the CI job actually fails when the README's quickstart block is broken."""
    markdown = """
## 30-second quickstart

```bash
false
echo unreachable
```
"""
    script = extract_quickstart_block(markdown)
    result = subprocess.run(  # noqa: S603 -- fixed argv, no shell, test-only
        ["bash", "-euo", "pipefail", "-c", script],  # noqa: S607 -- resolved via PATH, test-only
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0


def test_readme_quickstart_block_is_extractable() -> None:
    readme = Path(__file__).resolve().parents[1] / "README.md"
    block = extract_quickstart_block(readme.read_text(encoding="utf-8"))
    assert "context-report produce" in block
