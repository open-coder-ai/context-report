"""Restyles fig-catalog-status into the shared open-coder-ai visual language.

Same measurement as `paper/figures/make_figures.py`'s `fig_catalog_status` (18 public catalog
plugins x 4 measured attributes, one cell per statement's `result`) and the same data files;
only the rendering changes, from matplotlib to a light/dark SVG pair drawn with `palette.py`.

Run from this directory: `python make_catalog_status.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

import palette as p

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CATALOG_DIR = REPO / "paper" / "measurements" / "catalog-sample"
ORDER_FILE = REPO / "paper" / "figures" / "data" / "catalog_plugin_order.json"

# The same four attributes paper/figures/make_figures.py's STATUS_ATTRS puts in this grid.
ATTRS = [
    ("reachability", "reachability"),
    ("fault.malformedOutput", "malformed\ninput"),
    ("cost.latency_ms", "latency"),
    ("cost.context_tokens", "context\ntokens"),
]

# Every result this grid actually contains (verified against the committed statements): PASSED,
# FAILED and Error are three distinct, evidence-bearing outcomes -- the ENFORCEMENT ramp's three
# steps, ordered here from least to most cause for concern. NotApplicable is not a fourth grade of
# that ramp: it means the row does not apply (e.g. "declares no hooks"), which is absence of
# evidence, so it is always NEUTRAL, never a ramp colour.
GLYPHS = {"PASSED": "P", "Error": "E", "FAILED": "F", "NotApplicable": "-"}
RESULT_ORDER = ["PASSED", "Error", "FAILED", "NotApplicable"]

W = 700
MARGIN = 16
NAME_COL_W = 220
COL_W = 108
HEADER_TOP = 40
HEADER_H = 34
ROW_H = 22
GRID_X0 = MARGIN + NAME_COL_W
GRID_TOP = HEADER_TOP + HEADER_H + 6


def _load_plugins() -> list[dict]:
    """One entry per plugin, in `catalog_plugin_order.json`'s order (mirrors make_figures.py's
    `_load_catalog_plugins`, reimplemented here without the matplotlib import that module carries,
    since this generator must stay stdlib-only)."""
    order = json.loads(ORDER_FILE.read_text(encoding="utf-8"))
    plugins = []
    for entry in order:
        stmt = json.loads(
            (CATALOG_DIR / entry["marketplace"] / f"{entry['plugin']}.json").read_text(
                encoding="utf-8"
            )
        )
        rows = {row["attribute"]: row for row in stmt["predicate"]["attributes"]}
        plugins.append({"plugin": entry["plugin"], "rows": rows})
    return plugins


def _cell_colour(result: str, t: dict) -> str:
    if result == "NotApplicable":
        return t["neutral"]
    return t["enforcement"][RESULT_ORDER.index(result)]


def _cell_text_colour(result: str, t: dict) -> str:
    """Dark glyph on a light fill, light glyph on a dark fill; NEUTRAL always reads as text."""
    if result in ("Error", "FAILED"):
        return t["surface"]
    return t["text"]


def render(t: dict, name: str) -> str:  # noqa: ARG001 -- write_pair's render(t, name) contract
    plugins = _load_plugins()
    n = len(plugins)
    grid_bottom = GRID_TOP + n * ROW_H
    legend_y = grid_bottom + 28
    height = legend_y + 24

    svg = p.open_svg(
        W,
        height,
        t,
        "Catalog plugin status: 18 plugins by 4 measured attributes",
        "A grid of 18 public Claude Code plugins by reachability, malformed-input handling, "
        "latency and context tokens, one cell per statement's result. Three plugins fail "
        "reachability outright; every plugin that measures malformed-input handling passes it; "
        "cells marked not-applicable (dash, neutral grey) mean the row does not apply to that "
        "plugin, not that it scored low.",
    )

    svg += p.text(
        MARGIN,
        26,
        "one cell per statement's result, from the 18-plugin catalog sample",
        t["secondary"],
        12,
    )

    for col, (_attr, label) in enumerate(ATTRS):
        cx = GRID_X0 + col * COL_W + COL_W / 2
        lines = label.split("\n")
        y0 = HEADER_TOP + 14 if len(lines) == 1 else HEADER_TOP + 6
        for i, line in enumerate(lines):
            svg += p.text(cx, y0 + i * 14, line, t["text"], 11, weight="600", anchor="middle")

    for row, plugin in enumerate(plugins):
        y = GRID_TOP + row * ROW_H
        svg += p.text(
            MARGIN,
            y + ROW_H / 2 + 4,
            plugin["plugin"],
            t["text"],
            10,
            p.MONO,
        )
        for col, (attr, _label) in enumerate(ATTRS):
            result = plugin["rows"][attr]["result"]
            x = GRID_X0 + col * COL_W + p.GAP
            fill = _cell_colour(result, t)
            svg += p.box(x, y + p.GAP, COL_W - 2 * p.GAP, ROW_H - 2 * p.GAP, fill, rx=3)
            svg += p.text(
                x + (COL_W - 2 * p.GAP) / 2,
                y + ROW_H / 2 + 4,
                GLYPHS[result],
                _cell_text_colour(result, t),
                10,
                weight="600",
                anchor="middle",
            )

    entries = [
        (
            r,
            {
                "PASSED": "PASSED",
                "Error": "Error",
                "FAILED": "FAILED",
                "NotApplicable": "n/a (not applicable)",
            }[r],
        )
        for r in RESULT_ORDER
    ]
    entry_w = (W - 2 * MARGIN) / len(entries)
    for i, (result, label) in enumerate(entries):
        x = MARGIN + i * entry_w
        fill = _cell_colour(result, t)
        svg += p.box(x, legend_y, 16, 16, fill, rx=3)
        svg += p.text(
            x + 8,
            legend_y + 12,
            GLYPHS[result],
            _cell_text_colour(result, t),
            9,
            weight="600",
            anchor="middle",
        )
        svg += p.text(x + 22, legend_y + 12, label, t["secondary"], 11)

    return svg + p.close_svg()


if __name__ == "__main__":
    for path in p.write_pair("fig-catalog-status", render):
        print("wrote", path)
