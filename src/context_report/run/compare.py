"""Build the plain-text `context-report compare` table from recorded statements, no printing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from context_report.efficacy.row import VALUES_UNEXERCISED
from context_report.run import layout

BY_MODEL = "model"
BY_SUBJECT = "subject"


@dataclass(frozen=True)
class Cell:
    """One subject/model statement's efficacy row, and whether a judged file backed it."""

    subject_id: str
    model: str
    used_judged: bool
    row: dict[str, Any]


def _efficacy_attribute(stmt: dict[str, Any]) -> dict[str, Any]:
    return next(a for a in stmt["predicate"]["attributes"] if a["attribute"] == "efficacy")


def gather(out: Path, *, judged: bool) -> list[Cell]:
    """One Cell per recorded subject/model statement; `.judged.json` is preferred when asked."""
    cells: list[Cell] = []
    for subject_dir in sorted(p for p in out.iterdir() if p.is_dir()):
        for stmt_path in sorted(subject_dir.glob("*.json")):
            slug = stmt_path.stem
            if slug == "statement" or slug.endswith(".judged"):
                continue
            path, used_judged = stmt_path, False
            if judged:
                judged_path = subject_dir / f"{slug}.judged.json"
                if judged_path.is_file():
                    path, used_judged = judged_path, True
            stmt = json.loads(path.read_text(encoding="utf-8"))
            row = _efficacy_attribute(stmt)
            model = row.get("conditions", {}).get("model", slug)
            cells.append(Cell(subject_dir.name, model, used_judged, row))
    return cells


def _tokens(row: dict[str, Any]) -> int:
    """Input plus output tokens over both arms; `tokensPerArm` is keyed `with` / `without`."""
    per_arm = (row.get("values") or {}).get("tokensPerArm") or {}
    return sum(
        int(arm.get("inputTokens", 0)) + int(arm.get("outputTokens", 0))
        for arm in per_arm.values()
        if isinstance(arm, dict)
    )


_REASON_WIDTH = 40


def _short_reason(row: dict[str, Any]) -> str:
    """A one-line reason short enough for a table cell; the full text is in the statement itself."""
    reason = row.get("reasoning") or row["result"]
    return reason if len(reason) <= _REASON_WIDTH else reason[: _REASON_WIDTH - 1] + "…"


def _cell_text(row: dict[str, Any], *, unjudged_fallback: bool) -> str:
    est = row.get("estimate")
    if est is None:
        text = f"n/a ({_short_reason(row)})"
    else:
        ci = est["confidenceInterval"]
        text = (
            f"{est['pointEstimate']:+.2f} [{ci['lowerBound']:.2f}, {ci['upperBound']:.2f}] "
            f"{row['result']}"
        )
    return f"{text} (unjudged)" if unjudged_fallback else text


def _render(table: list[list[str]]) -> str:
    """A plain ASCII grid: two spaces between padded columns, a dashed rule under the header."""
    widths = [max(len(row[i]) for row in table) for i in range(len(table[0]))]
    lines = ["  ".join(cell.ljust(widths[j]) for j, cell in enumerate(table[0]))]
    lines.append("  ".join("-" * widths[j] for j in range(len(table[0]))))
    for row in table[1:]:
        lines.append("  ".join(cell.ljust(widths[j]) for j, cell in enumerate(row)))
    return "\n".join(lines)


def _rule_lists(cells: list[Cell]) -> dict[str, tuple[set[str], set[str]]]:
    """subject id -> (ungraded rule ids, unexercised rule ids), unioned across its models."""
    out: dict[str, tuple[set[str], set[str]]] = {}
    for cell in cells:
        values = cell.row.get("values") or {}
        ungraded, unexercised = out.setdefault(cell.subject_id, (set(), set()))
        ungraded.update(values.get("ungraded") or ())
        unexercised.update(values.get(VALUES_UNEXERCISED) or ())
    return out


def render_history(out: Path, *, rules: bool = False) -> str:
    """Every run under `out` side by side (the table `out/SUMMARY.md` holds); with `rules`, the
    same at rule level: adherence with / without, lift and verdict per rule in every run."""
    if rules:
        return layout.rule_history_markdown(Path(out))
    return layout.history_markdown(layout.load_index(Path(out)))


def render_table(
    out: Path, *, by: str = BY_MODEL, judged: bool = False, run_id: str | None = None
) -> str:
    """One run's comparison table (the latest under `out` unless `run_id`), then each subject's
    ungraded/unexercised rule ids, if any."""
    if by not in (BY_MODEL, BY_SUBJECT):
        raise ValueError(f"--by must be 'model' or 'subject', not {by!r}")
    try:
        out = layout.resolve_run_dir(Path(out), run_id)
    except ValueError:
        return "no recorded statements found under " + str(out)
    cells = gather(out, judged=judged)
    if not cells:
        return "no recorded statements found under " + str(out)

    row_attr, col_attr = ("model", "subject_id") if by == BY_MODEL else ("subject_id", "model")
    grid: dict[tuple[str, str], str] = {}
    totals: dict[str, int] = {}
    rows_seen: set[str] = set()
    cols_seen: set[str] = set()
    for cell in cells:
        r, c = getattr(cell, row_attr), getattr(cell, col_attr)
        rows_seen.add(r)
        cols_seen.add(c)
        grid[(r, c)] = _cell_text(cell.row, unjudged_fallback=judged and not cell.used_judged)
        totals[r] = totals.get(r, 0) + _tokens(cell.row)

    rows, cols = sorted(rows_seen), sorted(cols_seen)
    header = [by, *cols, "tokens/arm"]
    table = [header]
    for r in rows:
        row_cells = [grid.get((r, c), "n/a (not run)") for c in cols]
        table.append([r, *row_cells, str(totals[r])])

    lines = [_render(table), ""]
    for subject_id, (ungraded, unexercised) in sorted(_rule_lists(cells).items()):
        if not ungraded and not unexercised:
            continue
        lines.append(f"{subject_id}:")
        if ungraded:
            lines.append(f"  ungraded: {', '.join(sorted(ungraded))}")
        if unexercised:
            lines.append(f"  unexercised: {', '.join(sorted(unexercised))}")
    return "\n".join(lines).rstrip("\n")
