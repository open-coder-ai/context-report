"""Render `spec/` for GitHub Pages: every Markdown file also as HTML, the rest copied as is."""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import markdown

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "page.html"
_MD_LINK = re.compile(r'(href=")([^"#:]+?)\.md(["#])')
_H1 = re.compile(r"^#\s+(.+)$", re.M)


def render_markdown(text: str, fallback_title: str) -> str:
    """One Markdown document as a full HTML page; links to `.md` files point at their `.html`."""
    body = markdown.markdown(text, extensions=["fenced_code", "tables"])
    body = _MD_LINK.sub(r"\1\2.html\3", body)
    match = _H1.search(text)
    title = match.group(1).strip() if match else fallback_title
    return (
        TEMPLATE.read_text(encoding="utf-8").replace("__TITLE__", title).replace("__BODY__", body)
    )


def render_tree(src: Path, out: Path) -> list[Path]:
    """Copy `src` to `out`, write an `.html` beside every `.md`; return the HTML files written."""
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src, out)
    written = []
    for md in sorted(out.rglob("*.md")):
        html = md.with_suffix(".html")
        html.write_text(render_markdown(md.read_text(encoding="utf-8"), md.stem), encoding="utf-8")
        written.append(html)
    return written


def main(argv: list[str]) -> int:
    if len(argv) != 3:  # noqa: PLR2004 -- src and out
        print("usage: render_pages.py SRC_DIR OUT_DIR", file=sys.stderr)  # noqa: T201
        return 2
    written = render_tree(Path(argv[1]), Path(argv[2]))
    print(f"rendered {len(written)} page(s) into {argv[2]}")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
