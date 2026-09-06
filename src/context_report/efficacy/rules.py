"""Extract candidate rules from the instruction files an agent actually reads."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

DEFAULT_FILENAMES = ("CLAUDE.md", "AGENTS.md", ".cursorrules", ".windsurfrules")

_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$")
_HEADING = re.compile(r"^\s*#{1,6}\s")
_FENCE = re.compile(r"^\s*```")
_TABLE_ROW = re.compile(r"^\s*\|")
_HTML_COMMENT = re.compile(r"^\s*<!--")
_MARKDOWN_NOISE = re.compile(r"^\s*(?:>|\[!)")
_INLINE_FORMATTING = re.compile(r"[*_`]")

MIN_CHARS = 12
MAX_CHARS = 400

SKIP_TOO_SHORT = "too short to be a rule"
SKIP_TOO_LONG = "too long — prose, not a rule"
SKIP_NOT_DIRECTIVE = "reads as description, not instruction"


@dataclass(frozen=True)
class Rule:
    """One candidate rule, traceable to the line it came from."""

    id: str
    text: str
    source: str
    line: int


@dataclass(frozen=True)
class Extraction:
    """What was taken as rules, and — just as important — what was passed over and why."""

    rules: list[Rule]
    skipped: dict[str, int]

    def __len__(self) -> int:
        return len(self.rules)


def _markers() -> dict[str, list[str]]:
    path = files("context_report.data") / "efficacy" / "directive_markers.json"
    blob = path.read_text(encoding="utf-8")
    return json.loads(blob)


def is_directive(text: str) -> bool:
    """True when a line reads as an instruction to the agent rather than description."""
    markers = _markers()
    lowered = text.lower()
    first = lowered.split()[0].strip(":,.") if lowered.split() else ""
    if first in set(markers["imperative_openers"]):
        return True
    return any(re.search(rf"\b{re.escape(phrase)}\b", lowered) for phrase in markers["phrases"])


def _clean(text: str) -> str:
    return _INLINE_FORMATTING.sub("", text).strip()


def _is_break(raw: str) -> bool:
    return bool(
        not raw.strip()
        or _HEADING.match(raw)
        or _TABLE_ROW.match(raw)
        or _HTML_COMMENT.match(raw)
        or _MARKDOWN_NOISE.match(raw)
    )


def _blocks(text: str) -> list[tuple[int, str]]:
    """Logical rules, not physical lines — a bullet that wraps is one rule, joined back up."""
    out: list[tuple[int, str]] = []
    start, parts = 0, []
    in_fence = False

    def flush() -> None:
        if parts:
            out.append((start, _clean(" ".join(parts))))
            parts.clear()

    for number, raw in enumerate(text.splitlines(), start=1):
        if _FENCE.match(raw):
            flush()
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if _is_break(raw):
            flush()
            continue
        bullet = _BULLET.match(raw)
        if bullet or not parts:
            flush()
            start = number
            parts.append(bullet.group(1) if bullet else raw.strip())
            continue
        parts.append(raw.strip())
    flush()
    return out


def _skip_reason(text: str) -> str | None:
    if len(text) < MIN_CHARS:
        return SKIP_TOO_SHORT
    if len(text) > MAX_CHARS:
        return SKIP_TOO_LONG
    if not is_directive(text):
        return SKIP_NOT_DIRECTIVE
    return None


_SLUG_WORDS = 6
_SLUG_CHARS = 48


def slug(text: str) -> str:
    """A stable rule id from the rule's own words: "Never commit secrets." -> never-commit-secrets.

    A line number would change on every edit above the rule; the words change only when the
    rule does, which is when its measurements stop applying anyway.
    """
    words = re.findall(r"[a-z0-9]+", text.lower())[:_SLUG_WORDS]
    return "-".join(words)[:_SLUG_CHARS].rstrip("-") or "rule"


def extract(path: str | Path) -> Extraction:
    """Blocks that read as rules, plus a tally of what was passed over and why."""
    file = Path(path)
    rules: list[Rule] = []
    skipped: dict[str, int] = {}
    seen: dict[str, int] = {}
    for number, text in _blocks(file.read_text(encoding="utf-8")):
        reason = _skip_reason(text)
        if reason is not None:
            skipped[reason] = skipped.get(reason, 0) + 1
            continue
        base = slug(text)
        seen[base] = seen.get(base, 0) + 1
        rule_id = base if seen[base] == 1 else f"{base}-{seen[base]}"
        rules.append(Rule(id=rule_id, text=text, source=str(file), line=number))
    return Extraction(rules=rules, skipped=skipped)


def discover(root: str | Path = ".", filenames: tuple[str, ...] = DEFAULT_FILENAMES) -> list[Path]:
    """Instruction files present at the given root, in the order agents load them."""
    base = Path(root)
    return [base / name for name in filenames if (base / name).is_file()]


def extract_all(paths: list[Path]) -> Extraction:
    """Rules from several files, keeping source order, with the skips tallied across all of them."""
    rules: list[Rule] = []
    skipped: dict[str, int] = {}
    for path in paths:
        found = extract(path)
        rules.extend(found.rules)
        for reason, count in found.skipped.items():
            skipped[reason] = skipped.get(reason, 0) + count
    return Extraction(rules=rules, skipped=skipped)
