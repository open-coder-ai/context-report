"""The seam every producer builds on: rows fail early, statements bind and validate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from context_report import rows
from context_report.statement import Producer, Target, digest_path, schema, statement, validate

ROOT = Path(__file__).resolve().parents[1]


def _row(**over):
    base = {
        "attribute": "reachability",
        "basis": rows.RE_DERIVABLE,
        "result": rows.PASSED,
        "input_hash": rows.input_hash("reachability", "x"),
    }
    base.update(over)
    return rows.Row(**base)


def test_packaged_schema_is_byte_identical_to_spec():
    """Two copies exist so the package installs alone; a test, not discipline, keeps them equal."""
    spec = (ROOT / "spec/attestation/v0.1/schema.json").read_bytes()
    pkg = (ROOT / "src/context_report/data/attestation-v0.1.schema.json").read_bytes()
    assert spec == pkg


def test_input_hash_is_stable_and_order_sensitive():
    assert rows.input_hash("a", 1) == rows.input_hash("a", 1)
    assert rows.input_hash("a", 1) != rows.input_hash(1, "a")
    assert rows.input_hash("a").startswith("sha256:") and len(rows.input_hash("a")) == 7 + 64


def test_rederivable_row_requires_input_hash():
    with pytest.raises(ValueError, match="inputHash"):
        _row(input_hash=None)


def test_unmeasured_row_requires_reasoning():
    with pytest.raises(ValueError, match="must say why"):
        _row(result=rows.NOT_AVAILABLE)
    ok = rows.not_measured("interference", rows.NOT_AVAILABLE, "nothing co-installed")
    assert ok.to_dict()["reasoning"] == "nothing co-installed"


def test_efficacy_is_always_claimed():
    with pytest.raises(ValueError, match="always claimed"):
        _row(attribute="efficacy")


def test_unknown_attribute_needs_x_prefix():
    with pytest.raises(ValueError, match="x- prefix"):
        _row(attribute="vibes")
    assert _row(attribute="x-vibes").to_dict()["attribute"] == "x-vibes"


def test_measurement_from_samples_is_deterministic():
    m = rows.Measurement.from_samples([5, 1, 3, 2, 4], unit="ms")
    assert m.n == 5 and m.min == 1 and m.max == 5 and m.mean == 3
    assert m.percentiles == {"50": 3.0, "95": 5.0, "99": 5.0}
    assert rows.Measurement.from_samples([7], unit="ms").stddev == 0.0
    with pytest.raises(ValueError):
        rows.Measurement.from_samples([], unit="ms")


def test_digest_path_is_deterministic_and_ignores_git(tmp_path):
    (tmp_path / "b.txt").write_text("b")
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref")
    first = digest_path(tmp_path)
    (tmp_path / ".git" / "HEAD").write_text("changed")
    assert digest_path(tmp_path) == first
    (tmp_path / "a.txt").write_text("A")
    assert digest_path(tmp_path) != first


def test_statement_validates_against_the_schema(tmp_path):
    (tmp_path / "hook.sh").write_text("#!/bin/sh\nexit 0\n")
    stmt = statement(
        subject_name="hook",
        subject_sha256=digest_path(tmp_path),
        subject_kind="hook",
        target=Target("claude_code", client_version="1.0"),
        producer=Producer("https://example.com/wf@v1", {"context-report": "0.1.0"}),
        rows=[
            _row(),
            rows.Row(
                "cost.latency_ms",
                rows.RE_DERIVABLE,
                rows.PASSED,
                input_hash=rows.input_hash("lat"),
                environment_sensitive=True,
                measurement=rows.Measurement.from_samples([1.0, 2.0, 3.0], "ms"),
            ),
            rows.not_measured("fault.timeout", rows.NOT_AVAILABLE, "no client harness yet"),
        ],
        started_on="2026-09-05T10:00:00Z",
        finished_on="2026-09-05T10:01:00Z",
    )
    assert validate(stmt) == []
    assert json.dumps(stmt)  # serialisable


def test_statement_rejects_bad_kind_and_empty_rows():
    with pytest.raises(ValueError, match="subjectKind"):
        statement(
            subject_name="x",
            subject_sha256="0" * 64,
            subject_kind="gizmo",
            target=Target("a"),
            producer=Producer("https://p"),
            rows=[_row()],
        )
    with pytest.raises(ValueError, match="at least one row"):
        statement(
            subject_name="x",
            subject_sha256="0" * 64,
            subject_kind="hook",
            target=Target("a"),
            producer=Producer("https://p"),
            rows=[],
        )


def test_validate_reports_rather_than_raises():
    assert validate({"_type": "nope"})  # errors, no exception
    assert "predicateType" in json.dumps(schema())
