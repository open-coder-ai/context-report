"""Where a manifest's runs live: `out/runs/<run id>/` each, an index, and a history table."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNS_DIRNAME = "runs"
INDEX_FILENAME = "runs.json"
HISTORY_FILENAME = "SUMMARY.md"
MANIFEST_FILENAME = "manifest.json"
_ID_FORMAT = "%Y%m%dT%H%M%SZ"


def new_run_id() -> str:
    """A run id from the UTC clock, second resolution: sorts in time order as a plain string."""
    return datetime.now(timezone.utc).strftime(_ID_FORMAT)


def runs_dir(out: Path) -> Path:
    return Path(out) / RUNS_DIRNAME


def run_ids(out: Path) -> list[str]:
    """Every run recorded under `out`, oldest first."""
    root = runs_dir(out)
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir())


def resolve_run_dir(out: Path, run_id: str | None = None) -> Path:
    """`out/runs/<run_id>`, else the latest run under `out`, else `out` itself as one flat run.

    The flat form is the pre-history layout (a manifest and subject directories straight under
    `out`); it is still read so committed samples keep working.
    """
    out = Path(out)
    if run_id is not None:
        run_dir = runs_dir(out) / run_id
        if not (run_dir / MANIFEST_FILENAME).is_file():
            raise ValueError(f"no run {run_id!r} under {out} (have {run_ids(out)})")
        return run_dir
    ids = run_ids(out)
    if ids:
        return runs_dir(out) / ids[-1]
    if (out / MANIFEST_FILENAME).is_file():
        return out
    raise ValueError(f"no run found under {out}: nothing in {RUNS_DIRNAME}/ and no manifest.json")


def load_index(out: Path) -> list[dict[str, Any]]:
    path = Path(out) / INDEX_FILENAME
    if not path.is_file():
        return []
    return list(json.loads(path.read_text(encoding="utf-8")))


def record_run(out: Path, entry: dict[str, Any]) -> None:
    """Add (or replace, on resume) one run's entry in `runs.json` and rewrite the history table."""
    out = Path(out)
    index = [e for e in load_index(out) if e["runId"] != entry["runId"]]
    index.append(entry)
    index.sort(key=lambda e: e["runId"])
    (out / INDEX_FILENAME).write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / HISTORY_FILENAME).write_text(history_markdown(index), encoding="utf-8")


def _cell(row: dict[str, Any]) -> str:
    est = row.get("estimate")
    if not est:
        return row["result"]
    point, lower, upper = est
    return f"{row['result']} {point:+.1%} [{lower:+.1%}, {upper:+.1%}]"


def history_markdown(index: list[dict[str, Any]]) -> str:
    """One row per (subject, model), one column per run: what moved between runs, at a glance."""
    if not index:
        return "no runs recorded\n"
    keys: list[tuple[str, str]] = []
    cells: dict[tuple[str, str, str], str] = {}
    for entry in index:
        for row in entry["rows"]:
            key = (row["subject"], row["model"])
            if key not in keys:
                keys.append(key)
            cells[(row["subject"], row["model"], entry["runId"])] = _cell(row)
    ids = [e["runId"] for e in index]
    lines = [
        f"# Runs of this manifest ({len(index)})",
        "",
        "Each column is one run under `runs/<run id>/`; a cell is that run's pooled efficacy "
        "result and lift with its 95% interval. Read left to right for what a change moved.",
        "",
        "| subject | model | " + " | ".join(ids) + " |",
        "|---|---|" + "---|" * len(ids),
    ]
    for subject, model in keys:
        row_cells = [cells.get((subject, model, rid), "n/a (not run)") for rid in ids]
        lines.append(f"| {subject} | {model} | " + " | ".join(row_cells) + " |")
    lines.append("")
    for entry in index:
        lines.append(f"- `{entry['runId']}`: {entry['startedOn']} to {entry['finishedOn']}")
    return "\n".join(lines) + "\n"


def _statements(run_dir: Path) -> dict[tuple[str, str], dict[str, Any]]:
    """`(subject, model) -> efficacy row` of one run, preferring `.judged.json` where present."""
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for subject_dir in sorted(p for p in run_dir.iterdir() if p.is_dir()):
        for stmt_path in sorted(subject_dir.glob("*.json")):
            slug = stmt_path.stem
            if slug == "statement" or slug.endswith(".judged"):
                continue
            judged = subject_dir / f"{slug}.judged.json"
            doc = json.loads(
                (judged if judged.is_file() else stmt_path).read_text(encoding="utf-8")
            )
            row = next(
                (a for a in doc["predicate"]["attributes"] if a["attribute"] == "efficacy"), None
            )
            if row is None:
                continue
            model = row.get("conditions", {}).get("model", slug)
            rows[(subject_dir.name, model)] = row
    return rows


def _rule_cell(per_rule: dict[str, Any]) -> str:
    return (
        f"{per_rule['adherenceWith']:.0%} / {per_rule['adherenceWithout']:.0%} "
        f"({per_rule['lift']:+.0%}, {per_rule['verdict']})"
    )


def rule_history_markdown(out: Path) -> str:
    """One row per (subject, model, rule), one column per run: adherence with / without the rule,
    its lift and verdict, read from each run's statements. The change between the last two runs
    gets its own column, so an edited rule shows what it moved."""
    out = Path(out)
    ids = run_ids(out)
    if not ids:
        return "no runs recorded\n"
    per_run = {rid: _statements(runs_dir(out) / rid) for rid in ids}
    keys: list[tuple[str, str, str]] = []
    cells: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for rid in ids:
        for (subject, model), row in per_run[rid].items():
            for pr in (row.get("values") or {}).get("perRule") or []:
                key = (subject, model, pr["ruleId"])
                if key not in keys:
                    keys.append(key)
                cells[(*key, rid)] = pr
    delta_col = len(ids) > 1
    header = ["subject", "model", "rule", *ids] + (["last change"] if delta_col else [])
    intro = "A cell is adherence with / without the rule, then its lift and verdict, in that run."
    if delta_col:
        intro += " `last change` is the lift in the newest run minus the lift in the one before it."
    lines = [
        f"# Rules across runs of this manifest ({len(ids)})",
        "",
        intro,
        "",
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
    ]
    for subject, model, rule in keys:
        row_cells = [
            _rule_cell(cells[(subject, model, rule, rid)])
            if (subject, model, rule, rid) in cells
            else "n/a"
            for rid in ids
        ]
        if delta_col:
            last, prev = (
                cells.get((subject, model, rule, ids[-1])),
                cells.get((subject, model, rule, ids[-2])),
            )
            row_cells.append(f"{last['lift'] - prev['lift']:+.0%}" if last and prev else "n/a")
        lines.append(f"| {subject} | {model} | {rule} | " + " | ".join(row_cells) + " |")
    return "\n".join(lines) + "\n"
