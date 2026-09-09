"""The row-basis figure: what each row of a real report.json was concluded from.

Runs the README's own 30-second quickstart block fresh (the same mechanism the README's "Three
real rows" JSON block is pulled from -- see tools/quickstart_block.py and
tests/test_quickstart_block.py) and counts every row's basis in the resulting report.json, so this
figure can never disagree with the README: regenerating either regenerates from the same command.

Run from this directory: `python make_row_basis.py`. Needs `context-report` importable/installed
(as the repo's own CI already ensures before this job) so the extracted quickstart block's
`context-report produce` call resolves.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import palette as p

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
README = REPO / "README.md"

sys.path.insert(0, str(REPO / "tools"))
from quickstart_block import extract_quickstart_block  # noqa: E402 -- needs REPO on sys.path first

CLAIMED = "claimed"
# Mirrors context_report.rows.NOT_MEASURED: a result of NotAvailable, Error or NotApplicable
# means nothing was actually recomputed this run. Kept as a literal (not imported) so this
# generator stays stdlib-only -- importing context_report here would pull in its third-party
# dependencies (jsonschema, pyyaml) at figure-generation time.
NOT_MEASURED = frozenset({"NotAvailable", "Error", "NotApplicable"})

W, H = 700, 320
MARGIN = 16
BAR_MAX_W = W - 2 * MARGIN
MIN_INSIDE_LABEL_W = 24  # narrower than this, the count goes outside the bar instead


def _produce_fresh_report() -> dict:
    """Run the README's quickstart block in a scratch dir and return the report.json it writes.

    PYTHONPATH is pinned to this checkout's src/ so the block's `context-report` invocations
    import *this* commit's code even if another context-report checkout is also installed
    somewhere on this machine -- the figure must describe the commit it ships with, never a
    stray sibling checkout.
    """
    block = extract_quickstart_block(README.read_text(encoding="utf-8"))
    env = dict(os.environ)
    repo_src = str(REPO / "src")
    env["PYTHONPATH"] = (
        repo_src + os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else repo_src
    )
    with tempfile.TemporaryDirectory() as workdir:
        subprocess.run(  # noqa: S602 -- fixed, repo-owned script; same command the README documents
            block,
            shell=True,
            cwd=workdir,
            check=True,
            capture_output=True,
            text=True,
            executable="/bin/bash",
            env=env,
        )
        return json.loads((Path(workdir) / "report.json").read_text(encoding="utf-8"))


def _row_bases(stmt: dict) -> list[tuple[str, str, str]]:
    """(attribute, basis, result) for every row, in statement order."""
    return [
        (row["attribute"], row["basis"], row["result"]) for row in stmt["predicate"]["attributes"]
    ]


def _categorise(rows: list[tuple[str, str, str]]) -> dict[str, list[str]]:
    """Partition every row into exactly one of three mutually exclusive evidentiary bases.

    `claimed` (an author's assertion, schema basis "claimed") and `recomputed` (schema basis
    "re-derivable" AND a real, non-absent result) are the two evidence-bearing bases here -- only
    two, because that is what this real report actually contains; a third ramp colour is not used
    for a distinction the data does not carry. `absence` (re-derivable in principle, but this run's
    result is NotAvailable/Error/NotApplicable -- nothing was actually recomputed) is NEUTRAL: not
    a weaker grade of "recomputed", a different thing.
    """
    buckets: dict[str, list[str]] = {"recomputed": [], "claimed": [], "absence": []}
    for attribute, basis, result in rows:
        if basis == CLAIMED:
            buckets["claimed"].append(attribute)
        elif result in NOT_MEASURED:
            buckets["absence"].append(attribute)
        else:
            buckets["recomputed"].append(attribute)
    return buckets


BARS = [
    ("recomputed", "recomputed from the artifact", "re-derivable, and a real result was measured"),
    ("claimed", "the author's claim", "basis: claimed -- not independently checked this run"),
    ("absence", "not measured this run", "re-derivable in principle; NotAvailable/Error here"),
]


def _bar_colour(key: str, t: dict) -> str:
    return {"recomputed": t["enforcement"][2], "claimed": t["enforcement"][0]}.get(
        key, t["neutral"]
    )


def _hatch_id(name: str) -> str:
    return f"hatch-{name}"


def render(t: dict, name: str, buckets: dict[str, list[str]]) -> str:
    total = sum(len(v) for v in buckets.values())
    max_n = max(len(v) for v in buckets.values())
    row_block = 72
    bar_h = 20

    svg = p.open_svg(
        W,
        H,
        t,
        "Row bases in one context-report statement",
        f"Of {total} rows in the report.json the README's own quickstart block produces fresh, "
        f"{len(buckets['recomputed'])} are recomputed from the artifact, "
        f"{len(buckets['claimed'])} is the author's unverified claim, and "
        f"{len(buckets['absence'])} have not been measured this run -- shown as absence of "
        "evidence, not a weak score.",
    )

    svg += (
        f'  <pattern id="{_hatch_id(name)}" width="6" height="6" patternTransform="rotate(45)" '
        'patternUnits="userSpaceOnUse">\n'
        f'    <rect width="6" height="6" fill="{t["neutral"]}"/>\n'
        f'    <line x1="0" y1="0" x2="0" y2="6" stroke="{t["surface"]}" stroke-width="2"/>\n'
        "  </pattern>\n"
    )

    svg += p.text(
        MARGIN,
        26,
        f"report.json from the README's quickstart, run fresh -- {total} rows total",
        t["secondary"],
        12,
    )

    y = 48
    for key, label, sublabel in BARS:
        n = len(buckets[key])
        bar_w = (n / max_n) * BAR_MAX_W if max_n else 0
        svg += p.text(MARGIN, y, label, t["text"], 12, weight="600")
        svg += p.text(MARGIN, y + 15, sublabel, t["secondary"], 10)
        by = y + 22
        fill = f"url(#{_hatch_id(name)})" if key == "absence" else _bar_colour(key, t)
        if bar_w > 0:
            svg += p.box(MARGIN, by, bar_w, bar_h, fill, rx=3)
        inside = bar_w > MIN_INSIDE_LABEL_W
        if inside:
            text_colour = t["surface"] if key == "recomputed" else t["text"]
            svg += p.text(
                MARGIN + bar_w - 8,
                by + bar_h / 2 + 4,
                str(n),
                text_colour,
                12,
                weight="600",
                anchor="end",
            )
        else:
            svg += p.text(
                MARGIN + bar_w + 8, by + bar_h / 2 + 4, str(n), t["text"], 12, weight="600"
            )
        y += row_block

    svg += p.text(
        MARGIN,
        H - 14,
        "ordered by strength of evidence: recomputed > claimed > not measured "
        "(absence, not a lower grade)",
        t["secondary"],
        10,
    )

    return svg + p.close_svg()


if __name__ == "__main__":
    statement = _produce_fresh_report()
    rows = _row_bases(statement)
    row_buckets = _categorise(rows)
    for k, v in row_buckets.items():
        print(k, len(v), v)
    for path in p.write_pair("fig-row-basis", lambda t, n: render(t, n, row_buckets)):
        print("wrote", path)
