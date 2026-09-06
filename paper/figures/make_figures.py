"""Regenerates paper/figures/*.svg from the committed context-report statements.

Run from the repo root: `python paper/figures/make_figures.py [--chock-statements PATH]`.
Without `--chock-statements`, the chock dogfood numbers come from `data/chock_dogfood.json`,
a copy of the paper's own §5.1 table (the committed record). With it, the four target directories
under PATH (produced by `open-coder-ai/chock-catalog`, held off-repo) are read directly.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

import matplotlib

# Deterministic SVG output: same data in, same bytes out.
matplotlib.rcParams["svg.hashsalt"] = "context-report"
matplotlib.use("svg")
import matplotlib.pyplot as plt  # noqa: E402 -- backend must be set before this import
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CATALOG_DIR = REPO / "paper" / "measurements" / "catalog-sample"
DATA_DIR = HERE / "data"

SAVE_KW: dict[str, Any] = {"metadata": {"Date": None, "Creator": None}}

# Light-only palette with explicit backgrounds (dataviz skill's fallback for a standalone SVG
# embedded as an <img>, which has no page theme to inherit `currentColor` from).
BG = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

BLUE = "#2a78d6"  # "runs a local script" / hook-bearing
ORANGE = "#eb6834"  # "shells out through npx"
AQUA = "#1baf7a"  # no-hook plugin

GOOD = "#0ca30c"  # result: PASSED
CRITICAL = "#d03b3b"  # result: FAILED
SERIOUS = "#ec835a"  # result: Error
NOT_APPLICABLE_COLOR = "#c3c2b7"  # result: NotApplicable (neutral, not a status hue)

RESULT_COLORS = {
    "PASSED": GOOD,
    "FAILED": CRITICAL,
    "Error": SERIOUS,
    "NotApplicable": NOT_APPLICABLE_COLOR,
}
RESULT_ORDER = ["PASSED", "FAILED", "Error", "NotApplicable"]

INTERPRETER_FLOOR_MS = 13.0  # the interpreter-starting floor the dogfood measured (§4, §5.1)
CHOCK_CONTEXT_MEDIAN = 222  # chock's median cost.context_tokens per bundle (§5.1)

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Arial", "sans-serif"],
        "font.size": 10,
        "text.color": INK,
        "axes.edgecolor": AXIS,
        "axes.labelcolor": INK_SECONDARY,
        "xtick.color": INK_SECONDARY,
        "ytick.color": INK_SECONDARY,
        "axes.facecolor": BG,
        "figure.facecolor": BG,
        "savefig.facecolor": BG,
        "grid.color": GRID,
    }
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _rows_by_attribute(statement: dict) -> dict[str, dict]:
    return {row["attribute"]: row for row in statement["predicate"]["attributes"]}


def _load_catalog_plugins() -> list[dict]:
    """One entry per plugin, in `data/catalog_plugin_order.json`'s order (SUMMARY.md's table)."""
    order = _load_json(DATA_DIR / "catalog_plugin_order.json")
    plugins = []
    for entry in order:
        statement = _load_json(CATALOG_DIR / entry["marketplace"] / f"{entry['plugin']}.json")
        rows = _rows_by_attribute(statement)
        plugins.append({**entry, "rows": rows})
    return plugins


def _is_hook_bearing(rows: dict[str, dict]) -> bool:
    """True unless the reachability row's own reasoning says the plugin declares no hooks."""
    reach = rows["reachability"]
    if reach["result"] != "NotApplicable":
        return True
    return "declares no hooks" not in reach.get("reasoning", "")


def _pre_tool_command(rows: dict[str, dict]) -> str | None:
    hooks = rows["reachability"].get("conditions", {}).get("hooks") or []
    return hooks[0]["command"] if hooks else None


def _interpreter_kind(command: str | None) -> str:
    if command and "npx" in command:
        return "npx"
    return "local"


def _any_would_allow(values: Any) -> bool:
    """True if any nested case dict under a fault.malformedOutput row has `would_allow: true`.

    Handles both the catalog schema (`values.wouldAllowAny` plus a `perHook` nesting) and chock's
    single-hook-per-statement shape (case dicts directly under `values`), by searching either.
    """
    if isinstance(values, dict):
        if values.get("would_allow") is True:
            return True
        return any(_any_would_allow(v) for v in values.values())
    return False


def _load_chock(chock_statements: Path | None) -> list[dict]:
    """Per-target chock numbers: from --chock-statements if given, else the paper's own table."""
    fallback = _load_json(DATA_DIR / "chock_dogfood.json")["targets"]
    if chock_statements is None:
        return fallback
    dir_names = {
        "claude_code": "claude",
        "codex": "codex",
        "copilot": "copilot",
        "cursor": "cursor",
    }

    targets = []
    for row in fallback:
        target_dir = chock_statements / dir_names[row["key"]]
        resolved = sorted(target_dir.glob("*.resolved.json"))
        unresolved = sorted(target_dir.glob("*.unresolved.json"))
        reach_resolved = 0
        reach_unresolved = 0
        allow_resolved = 0
        p50s, p95s = [], []
        commands = []
        for path in resolved:
            st = _rows_by_attribute(_load_json(path))
            if st["reachability"]["result"] == "PASSED":
                reach_resolved += 1
            fault = st["fault.malformedOutput"]
            if _any_would_allow(fault.get("values")):
                allow_resolved += 1
            lat = st["cost.latency_ms"].get("measurement")
            if lat:
                p50s.append(lat["percentiles"]["50"])
                p95s.append(lat["percentiles"]["95"])
            commands.append(st["reachability"].get("conditions", {}).get("command", ""))
        for path in unresolved:
            st = _rows_by_attribute(_load_json(path))
            if st["reachability"]["result"] == "PASSED":
                reach_unresolved += 1
        targets.append(
            {
                **row,
                "reachable_resolved": reach_resolved,
                "reachable_unresolved": reach_unresolved,
                "allow_malformed_resolved": allow_resolved,
                "latency_p50_ms": statistics.median(p50s) if p50s else row["latency_p50_ms"],
                "latency_p95_ms": statistics.median(p95s) if p95s else row["latency_p95_ms"],
                "interpreter": "npx" if any("npx" in c for c in commands) else "local",
            }
        )
    return targets


def _write_svg(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Figure 1: fig-pipeline.svg (hand-drawn)
# ---------------------------------------------------------------------------


def fig_pipeline(path: Path) -> None:
    """Author's CI to catalog verdict: five boxes, the re-derivable/claimed fork made explicit."""
    svg = f"""
<svg viewBox="0 0 900 340" xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="Author's CI runs the producer, which emits a statement bound to the artifact
     digest. The catalog recomputes the re-derivable rows and emits a recomputation plus a
     verdict; claimed rows are shown as author-reported, never as proof.">
  <rect width="900" height="340" fill="{BG}"/>
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7"
            orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="{INK}"/>
    </marker>
  </defs>
  <style>
    .box {{ fill: {BG}; stroke: {INK}; stroke-width: 1.5; }}
    .lbl {{ font: 13px sans-serif; fill: {INK}; text-anchor: middle; }}
    .arrlbl {{ font: 12px sans-serif; fill: {INK_SECONDARY}; text-anchor: middle; }}
    .edge {{ fill: none; stroke: {INK}; stroke-width: 1.5; marker-end: url(#arrow); }}
  </style>

  <!-- Box A: author's CI -->
  <rect class="box" x="20" y="140" width="150" height="60" rx="6"/>
  <text class="lbl" x="95" y="174">Author's CI runs</text>
  <text class="lbl" x="95" y="190">the producer</text>

  <!-- Box B: statement -->
  <rect class="box" x="230" y="140" width="180" height="60" rx="6"/>
  <text class="lbl" x="320" y="166">Statement bound to</text>
  <text class="lbl" x="320" y="182">the artifact digest</text>

  <path class="edge" d="M170,170 L226,170"/>
  <text class="arrlbl" x="198" y="160">produce</text>

  <!-- Fork: re-derivable rows (top) vs claimed rows (bottom) -->
  <path class="edge" d="M410,155 C 470,110 500,75 540,75"/>
  <text class="arrlbl" x="470" y="95">re-derivable rows</text>

  <path class="edge" d="M410,185 C 470,235 500,270 540,270"/>
  <text class="arrlbl" x="475" y="255">claimed rows</text>

  <!-- Box C: catalog recomputes -->
  <rect class="box" x="540" y="45" width="190" height="60" rx="6"/>
  <text class="lbl" x="635" y="71">Catalog recomputes</text>
  <text class="lbl" x="635" y="87">the re-derivable rows</text>

  <path class="edge" d="M730,75 L790,75 L790,160 L 760,160"/>

  <!-- Box D: recomputation + verdict -->
  <rect class="box" x="600" y="130" width="220" height="60" rx="6"/>
  <text class="lbl" x="710" y="156">Catalog emits a</text>
  <text class="lbl" x="710" y="172">recomputation + a verdict</text>

  <!-- Box E: claimed rows, never proof -->
  <rect class="box" x="540" y="240" width="280" height="70" rx="6"/>
  <text class="lbl" x="680" y="266">claimed rows shown as</text>
  <text class="lbl" x="680" y="282">author-reported, never proof</text>
  <text class="lbl" x="680" y="298">(no recomputation attempted)</text>
</svg>
"""
    _write_svg(path, svg)


# ---------------------------------------------------------------------------
# Figure 2: fig-two-models.svg (hand-drawn)
# ---------------------------------------------------------------------------


def fig_two_models(path: Path) -> None:
    """The paired ablation: one subject model, two arms, a judge with a deterministic bypass."""
    svg = f"""
<svg viewBox="0 0 720 400" xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="One subject model (conditions.model) runs two arms, with the artifact and
     without. Both arms feed a judge model (conditions.judgeModel) that grades them against the
     rule's criterion; a deterministic grader bypasses the judge model directly to the verdict
     when the criterion is machine-checkable.">
  <rect width="720" height="400" fill="{BG}"/>
  <defs>
    <marker id="arrow2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7"
            orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="{INK}"/>
    </marker>
  </defs>
  <style>
    .box {{ fill: {BG}; stroke: {INK}; stroke-width: 1.5; }}
    .lbl {{ font: 13px sans-serif; fill: {INK}; text-anchor: middle; }}
    .sub {{ font: 11px sans-serif; fill: {INK_SECONDARY}; text-anchor: middle; }}
    .arrlbl {{ font: 11px sans-serif; fill: {INK_SECONDARY}; text-anchor: middle; }}
    .edge {{ fill: none; stroke: {INK}; stroke-width: 1.5; marker-end: url(#arrow2); }}
    .bypass {{ fill: none; stroke: {ORANGE}; stroke-width: 1.5; stroke-dasharray: 5 4;
               marker-end: url(#arrow2); }}
  </style>

  <!-- Subject model -->
  <rect class="box" x="260" y="15" width="200" height="55" rx="6"/>
  <text class="lbl" x="360" y="38">Subject model</text>
  <text class="sub" x="360" y="54">conditions.model</text>

  <path class="edge" d="M320,70 L200,140"/>
  <path class="edge" d="M400,70 L520,140"/>

  <!-- Arm boxes -->
  <rect class="box" x="100" y="140" width="200" height="55" rx="6"/>
  <text class="lbl" x="200" y="163">With the artifact</text>
  <text class="sub" x="200" y="179">rule text prepended</text>

  <rect class="box" x="420" y="140" width="200" height="55" rx="6"/>
  <text class="lbl" x="520" y="163">Without the artifact</text>
  <text class="sub" x="520" y="179">control arm</text>

  <!-- Both arms into judge -->
  <path class="edge" d="M220,195 L300,255"/>
  <path class="edge" d="M500,195 L420,255"/>

  <!-- Judge model -->
  <rect class="box" x="260" y="255" width="200" height="55" rx="6"/>
  <text class="lbl" x="360" y="278">Judge model</text>
  <text class="sub" x="360" y="294">conditions.judgeModel</text>

  <path class="edge" d="M360,310 L360,345"/>
  <text class="arrlbl" x="440" y="330">grades against the rule's criterion</text>

  <!-- Deterministic bypass around the judge -->
  <path class="bypass" d="M120,195 C 40,260 40,330 150,350"/>
  <path class="bypass" d="M600,195 C 680,260 680,330 570,350"/>
  <text class="arrlbl" x="60" y="280" fill="{ORANGE}">deterministic grader</text>
  <text class="arrlbl" x="60" y="294" fill="{ORANGE}">bypasses the judge</text>

  <!-- Verdict -->
  <rect class="box" x="260" y="345" width="200" height="45" rx="6"/>
  <text class="lbl" x="360" y="373">Verdict per rule</text>
</svg>
"""
    _write_svg(path, svg)


# ---------------------------------------------------------------------------
# Figure 4: fig-catalog-status.svg
# ---------------------------------------------------------------------------

STATUS_ATTRS = [
    ("reachability", "reachability"),
    ("fault.malformedOutput", "malformed\ninput"),
    ("cost.latency_ms", "latency"),
    ("cost.context_tokens", "context\ntokens"),
]


def fig_catalog_status(path: Path, plugins: list[dict]) -> None:
    """18 plugins x 4 attributes, each cell coloured by its statement's `result`.

    Drawn as individual Rectangle patches, not imshow: imshow rasterizes to an embedded PNG even
    in an SVG, and that base64 blob's high entropy trips secret-scanning hooks as a false positive.
    """
    n = len(plugins)
    m = len(STATUS_ATTRS)
    grid = [[p["rows"][attr]["result"] for attr, _ in STATUS_ATTRS] for p in plugins]

    fig, ax = plt.subplots(figsize=(6.4, 0.34 * n + 1.6))
    for row, results in enumerate(grid):
        for col, result in enumerate(results):
            ax.add_patch(
                plt.Rectangle(
                    (col - 0.5, row - 0.5), 1, 1, facecolor=RESULT_COLORS[result], edgecolor=BG
                )
            )

    ax.set_xticks(range(m))
    ax.set_xticklabels([label for _, label in STATUS_ATTRS])
    ax.xaxis.tick_top()
    ax.set_yticks(range(n))
    ax.set_yticklabels([p["plugin"] for p in plugins])
    ax.tick_params(length=0)
    ax.set_xlim(-0.5, m - 0.5)
    ax.set_ylim(n - 0.5, -0.5)

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks([x - 0.5 for x in range(m + 1)], minor=True)
    ax.set_yticks([y - 0.5 for y in range(n + 1)], minor=True)
    ax.grid(which="minor", color=BG, linewidth=2)
    ax.tick_params(which="minor", length=0)

    handles = [Patch(facecolor=RESULT_COLORS[r], label=r) for r in RESULT_ORDER]
    ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.012),
        ncol=4,
        frameon=False,
        fontsize=9,
        handlelength=1.2,
    )
    fig.suptitle(
        "18 catalog plugins x 4 attributes, coloured by measured result", fontsize=11, y=1.0
    )
    fig.savefig(path, format="svg", bbox_inches="tight", **SAVE_KW)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 5: fig-latency.svg
# ---------------------------------------------------------------------------


def fig_latency(path: Path, plugins: list[dict], chock: list[dict]) -> None:
    """Per-hook p50 (bar) to p95 (whisker), log-scale ms; local script vs npx; the 13 ms floor."""
    rows = []
    for p in plugins:
        lat = p["rows"]["cost.latency_ms"]
        if lat["result"] != "PASSED":
            continue
        m = lat["measurement"]
        kind = _interpreter_kind(_pre_tool_command(p["rows"]))
        rows.append((p["plugin"], m["percentiles"]["50"], m["percentiles"]["95"], kind))
    for t in chock:
        name = f"chock/{t['label']}"
        rows.append((name, t["latency_p50_ms"], t["latency_p95_ms"], t["interpreter"]))
    rows.sort(key=lambda r: r[1])

    fig, ax = plt.subplots(figsize=(6.4, 0.42 * len(rows) + 1.1))
    y = range(len(rows))
    colors = {"local": BLUE, "npx": ORANGE}
    for i, (_name, p50, p95, kind) in enumerate(rows):
        ax.plot([p50, p95], [i, i], color=colors[kind], linewidth=6, solid_capstyle="round")
        ax.plot(p50, i, "o", color=INK, markersize=3, zorder=3)

    top = len(rows) - 0.3
    ax.axvline(INTERPRETER_FLOOR_MS, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(
        INTERPRETER_FLOOR_MS,
        top + 0.55,
        " 13 ms interpreter floor",
        color=INK_SECONDARY,
        fontsize=8,
        va="top",
    )

    ax.set_xscale("log")
    ax.set_yticks(list(y))
    ax.set_yticklabels([r[0] for r in rows], fontsize=9)
    ax.set_xlabel("p50-p95 latency per hook invocation, ms (log scale)")
    ax.set_ylim(-0.7, top + 0.9)
    ax.grid(axis="x", which="both", linewidth=0.5, alpha=0.6)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)

    handles = [
        Line2D([0], [0], color=BLUE, linewidth=6, label="runs a local script"),
        Line2D([0], [0], color=ORANGE, linewidth=6, label="shells out through npx"),
    ]
    ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=9)
    ax.set_title("Per-hook latency: p50 to p95, catalog sample + chock dogfood", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, format="svg", bbox_inches="tight", **SAVE_KW)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 6: fig-context-tokens.svg
# ---------------------------------------------------------------------------


def fig_context_tokens(path: Path, plugins: list[dict]) -> None:
    """Sorted horizontal bars of cost.context_tokens; the no-text plugin is a labelled gap."""
    rows = []
    no_text = []
    for p in plugins:
        ctx = p["rows"]["cost.context_tokens"]
        hook_bearing = _is_hook_bearing(p["rows"])
        if ctx["result"] == "NotApplicable":
            no_text.append(p["plugin"])
            continue
        rows.append((p["plugin"], ctx["measurement"]["mean"], hook_bearing))
    rows.sort(key=lambda r: r[1])
    # Place the no-text plugin(s) at the low end of the sort, as a gap rather than a zero bar.
    for name in no_text:
        rows.insert(0, (name, None, True))

    fig, ax = plt.subplots(figsize=(6.4, 0.4 * len(rows) + 1.0))
    y = range(len(rows))
    min_tok = min(v for _, v, _ in rows if v is not None)
    for i, (_name, tokens, hook_bearing) in enumerate(rows):
        color = BLUE if hook_bearing else AQUA
        if tokens is None:
            ax.barh(
                i, min_tok * 0.35, color="none", edgecolor=MUTED, linewidth=1, linestyle=(0, (3, 2))
            )
            ax.text(
                min_tok * 0.37,
                i,
                "no text (not zero)",
                va="center",
                fontsize=8,
                color=INK_SECONDARY,
            )
        else:
            ax.barh(i, tokens, color=color)
            ax.text(
                tokens * 1.05, i, f"{tokens:,.0f}", va="center", fontsize=8, color=INK_SECONDARY
            )

    top = len(rows) - 0.3
    ax.axvline(CHOCK_CONTEXT_MEDIAN, color=MUTED, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(
        CHOCK_CONTEXT_MEDIAN,
        top + 0.55,
        " chock median (222)",
        color=INK_SECONDARY,
        fontsize=8,
        va="top",
    )

    ax.set_xscale("log")
    ax.set_yticks(list(y))
    ax.set_yticklabels([r[0] for r in rows], fontsize=9)
    ax.set_xlabel("estimated context tokens per plugin, approx-regex-v1 (log scale)")
    ax.set_ylim(-0.7, top + 0.9)
    ax.grid(axis="x", which="both", linewidth=0.5, alpha=0.6)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)

    handles = [
        Patch(facecolor=BLUE, label="hook-bearing"),
        Patch(facecolor=AQUA, label="no hook"),
    ]
    ax.legend(handles=handles, loc="lower right", frameon=False, fontsize=9)
    ax.set_title("Context weight per catalog plugin, sorted", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, format="svg", bbox_inches="tight", **SAVE_KW)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 3: fig-chock-reachability.svg
# ---------------------------------------------------------------------------


def fig_chock_reachability(path: Path, chock: list[dict]) -> None:
    """Grouped bars: hooks reachable with vs without the plugin-root variable, per chock target."""
    labels = [t["label"] for t in chock]
    x = range(len(labels))
    width = 0.32

    fig, ax = plt.subplots(figsize=(6.0, 3.0))
    set_vals = [t["reachable_resolved"] for t in chock]
    unset_vals = [t["reachable_unresolved"] for t in chock]
    ax.bar([i - width / 2 for i in x], set_vals, width, color=BLUE, label="variable set")
    ax.bar([i + width / 2 for i in x], unset_vals, width, color=ORANGE, label="variable unset")

    for i, t in enumerate(chock):
        ax.plot(i, t["allow_malformed_resolved"] + 0.15, marker="D", color=INK, markersize=6)

    ax.plot(
        [],
        [],
        marker="D",
        color=INK,
        linestyle="none",
        markersize=6,
        label="allows on malformed input",
    )

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("hooks reachable, of 4")
    ax.set_ylim(0, 4.8)
    ax.set_yticks(range(5))
    ax.grid(axis="y", linewidth=0.5, alpha=0.6)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), ncol=1, frameon=False, fontsize=8)
    ax.set_title("chock hook reachability: plugin-root variable set vs unset", fontsize=11)
    fig.savefig(path, format="svg", bbox_inches="tight", **SAVE_KW)
    plt.close(fig)


# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--chock-statements",
        type=Path,
        default=None,
        help="path to the chock dogfood statements (held off-repo); omit to use the paper's table",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=HERE,
        help="directory to write the SVGs into (default: this figures/ dir)",
    )
    args = parser.parse_args()

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    plugins = _load_catalog_plugins()
    chock = _load_chock(args.chock_statements)

    fig_pipeline(out_dir / "fig-pipeline.svg")
    fig_two_models(out_dir / "fig-two-models.svg")
    fig_catalog_status(out_dir / "fig-catalog-status.svg", plugins)
    fig_latency(out_dir / "fig-latency.svg", plugins, chock)
    fig_context_tokens(out_dir / "fig-context-tokens.svg", plugins)
    fig_chock_reachability(out_dir / "fig-chock-reachability.svg", chock)


if __name__ == "__main__":
    main()
