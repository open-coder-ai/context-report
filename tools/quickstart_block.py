"""Extract the first fenced ```bash block under the README's quickstart heading, stdlib only."""

from __future__ import annotations

import sys
from pathlib import Path

HEADING = "## 30-second quickstart"


def extract_quickstart_block(markdown: str, heading: str = HEADING) -> str:
    """The body of the first ```bash fence after `heading`, up to the next `##` heading."""
    lines = markdown.splitlines()
    try:
        start = lines.index(heading)
    except ValueError:
        raise ValueError(f"heading {heading!r} not found") from None
    in_block = False
    block: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## ") and not in_block:
            break
        if not in_block:
            if line.strip() == "```bash":
                in_block = True
            continue
        if line.strip() == "```":
            return "\n".join(block) + "\n"
        block.append(line)
    raise ValueError(f"no closed fenced bash block found under {heading!r}")


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else Path("README.md")
    sys.stdout.write(extract_quickstart_block(path.read_text(encoding="utf-8")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
