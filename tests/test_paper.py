"""Structural checks on the paper skeleton: every placeholder is tracked, every citation resolves,
and the register stays plain.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper" / "context-report.md"
REFERENCES = ROOT / "paper" / "references.md"

PAPER_TEXT = PAPER.read_text(encoding="utf-8")
REFERENCES_TEXT = REFERENCES.read_text(encoding="utf-8")

# Every `[[...]]` placeholder that currently appears in the paper. A number landing under
# `measurements/` should replace the placeholder text *and* remove its entry here in the same
# change, so this set can never silently drift ahead of or behind the document.
PLACEHOLDERS = {
    "[[N catalog plugins]]",
    "[[N dogfood bundles measured]]",
    "[[N plugins]]",
    "[[N target agents]]",
    "[[X% fail open on timeout]]",
    "[[artifact one]]",
    "[[artifact two]]",
    "[[catalog list]]",
    "[[catalog name]]",
    "[[confirm with W3/W4: canonical cwd set tested per target agent]]",
    "[[confirm with W3/W4: timing mechanism, n, and environment fields recorded]]",
    "[[confirm with W3/W4: tokenizer approximation used and its disclosed error bound]]",
    "[[confirm with W3/W4: which fault rows need a live client vs. oracle-only, and the sandboxing "
    "approach]]",
    "[[latency p50]]",
    "[[latency p95]]",
    "[[match or mismatch]]",
    "[[mean context tokens added per artifact]]",
    "[[mean tokens]]",
    "[[measured posture]]",
    "[[median Y ms per tool call]]",
    "[[plugin name]]",
    "[[result]]",
    "[[sampling method]]",
    "[[target agent]]",
}

BANNED_PHRASES = ("revolutionary", "first-ever", "nobody has ever", "game-changing")


def _placeholders_in_paper() -> set[str]:
    """Every `[[...]]` span in the paper, read whole so a line-wrapped placeholder still matches."""
    return set(re.findall(r"\[\[[^\[\]]*\]\]", PAPER_TEXT))


def _citations_in_paper() -> set[int]:
    """Every `[n]` numeric citation, excluding the `[[n]]`-shaped placeholders above."""
    without_placeholders = re.sub(r"\[\[[^\[\]]*\]\]", "", PAPER_TEXT)
    return {int(n) for n in re.findall(r"(?<!\[)\[(\d+)\](?!\])", without_placeholders)}


def _reference_numbers() -> set[int]:
    """Numbered list entries in references.md: a line starting the item, e.g. '12. **Title**.'"""
    return {int(n) for n in re.findall(r"^(\d+)\.\s", REFERENCES_TEXT, flags=re.MULTILINE)}


def test_every_placeholder_in_the_paper_is_tracked() -> None:
    found = _placeholders_in_paper()
    untracked = found - PLACEHOLDERS
    assert not untracked, f"placeholders in the paper missing from PLACEHOLDERS: {untracked}"


def test_placeholders_set_has_no_stale_entries() -> None:
    """A PLACEHOLDERS entry the paper no longer contains is the drift this test exists to catch."""
    found = _placeholders_in_paper()
    stale = PLACEHOLDERS - found
    assert not stale, f"PLACEHOLDERS entries no longer present in the paper: {stale}"


def test_every_citation_has_a_reference_entry() -> None:
    cited = _citations_in_paper()
    available = _reference_numbers()
    missing = cited - available
    assert not missing, f"citations with no entry in references.md: {sorted(missing)}"


def test_references_has_no_unused_entries() -> None:
    """Every numbered entry in references.md should back at least one citation in the paper."""
    cited = _citations_in_paper()
    available = _reference_numbers()
    unused = available - cited
    assert not unused, f"references.md entries never cited in the paper: {sorted(unused)}"


def test_no_sales_language() -> None:
    lines = PAPER_TEXT.splitlines()
    offenders = [
        (i, line)
        for i, line in enumerate(lines, start=1)
        for phrase in BANNED_PHRASES
        if phrase in line.lower()
    ]
    assert not offenders, f"sales language found: {offenders}"


def test_placeholders_are_not_empty() -> None:
    """Guards against a future edit collapsing a placeholder to `[[]]`, matching everything."""
    assert all(len(p) > 4 for p in PLACEHOLDERS)
