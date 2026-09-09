"""GitHub social-preview card: repo name, one line of what it is, one real number. Light only --
GitHub's social preview has no dark variant. No logo: this repo has none in docs/assets/.

Run from this directory: `python make_social_card.py`. Rendering the PNG needs `cairosvg`; if it
is not installed (as in CI, which never needs it -- see docs/figures/make_row_basis.py) the SVG is
still written and the PNG step is skipped rather than failing the regeneration.
"""

from __future__ import annotations

from pathlib import Path

import palette as p
from make_row_basis import _categorise, _produce_fresh_report, _row_bases

HERE = Path(__file__).resolve().parent
W, H = 1280, 640

TAGLINE = "an open, signed report of whether an agent context artifact actually works"


def _headline_number() -> str:
    """The same real report make_row_basis.py draws from, reduced to one number for the card."""
    buckets = _categorise(_row_bases(_produce_fresh_report()))
    total = sum(len(v) for v in buckets.values())
    return f"{len(buckets['recomputed'])} of {total} rows recomputed from the artifact, fresh"


def render(number: str) -> str:
    t = p.theme("light")
    svg = p.open_svg(
        W,
        H,
        t,
        "context-report",
        "context-report: an open, signed report of whether an agent context artifact actually "
        f"works. {number}.",
    )
    accent = t["enforcement"][2]
    svg += p.box(0, 0, 14, H, accent, rx=0)
    svg += p.text(72, 260, "context-report", t["text"], 64, p.MONO, "600")
    svg += p.text(72, 320, TAGLINE, t["secondary"], 26)
    svg += p.box(72, 380, 760, 3, t["neutral"], rx=0)
    svg += p.text(72, 440, number, accent, 30, p.MONO, "600")
    return svg + p.close_svg()


def main() -> None:
    number = _headline_number()
    print(number)
    svg_path = HERE / "social-card.svg"
    svg_path.write_text(render(number).strip() + "\n", encoding="utf-8")
    print("wrote", svg_path)

    try:
        import cairosvg
    except ImportError:
        print("cairosvg not installed -- skipping PNG render (not needed in CI)")
        return
    png_path = HERE / "social-card.png"
    cairosvg.svg2png(url=str(svg_path), write_to=str(png_path), output_width=W, output_height=H)
    print("wrote", png_path)


if __name__ == "__main__":
    main()
