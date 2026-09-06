"""`produce_statement` accepts a measured efficacy row and the run's byproducts."""

from __future__ import annotations

from pathlib import Path

import pytest

from context_report.efficacy.grade import Graded
from context_report.efficacy.row import efficacy_row
from context_report.produce.run import produce_statement
from context_report.rows import NOT_APPLICABLE, NOT_AVAILABLE, not_measured
from context_report.statement import validate


def test_measured_efficacy_row_and_byproducts_land_in_a_valid_statement(tmp_path: Path) -> None:
    agents = tmp_path / "AGENTS.md"
    agents.write_text("- Never commit secrets.\n")
    row = efficacy_row(
        Graded(ungraded=("never-commit-secrets",)),
        model="anthropic/m",
        judge_model=None,
        measured_on="2026-09-06",
        n_per_arm=2,
        transcripts=4,
    )
    stmt = produce_statement(
        subject=agents,
        subject_kind="instruction-file",
        target="claude_code",
        efficacy_row=row,
        byproducts=[{"name": "transcripts", "digest": {"sha256": "ab" * 32}}],
    )
    assert validate(stmt) == []
    eff = next(a for a in stmt["predicate"]["attributes"] if a["attribute"] == "efficacy")
    assert eff["result"] == NOT_AVAILABLE and eff["conditions"]["model"] == "anthropic/m"
    assert stmt["predicate"]["byproducts"][0]["name"] == "transcripts"


def test_a_non_efficacy_row_is_refused(tmp_path: Path) -> None:
    agents = tmp_path / "AGENTS.md"
    agents.write_text("- x\n")
    with pytest.raises(ValueError, match="efficacy row"):
        produce_statement(
            subject=agents,
            subject_kind="instruction-file",
            target="claude_code",
            efficacy_row=not_measured("decision", NOT_APPLICABLE, "nope"),
        )
