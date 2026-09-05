"""The verifier: well-formed + bound checks, recomputation of re-derivable rows, and the SVR."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from context_report.rows import CLAIMED, RE_DERIVABLE
from context_report.statement import digest_path
from context_report.verify import (
    Diff,
    InputHashPresenceRecomputer,
    Verification,
    recompute_rows,
    to_svr,
    verify_statement,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = json.loads(
    (ROOT / "spec/attestation/v0.1/examples/plugin-copilot.json").read_text(encoding="utf-8")
)


def _row(instance: dict, name: str) -> dict:
    return next(a for a in instance["predicate"]["attributes"] if a["attribute"] == name)


def test_the_worked_example_is_ok_with_no_subject_path():
    v = verify_statement(EXAMPLE)
    assert v.schema_errors == []
    assert v.subject_digest_matches is None
    assert v.ok is True


def test_example_sorts_rows_into_claimed_rederivable_and_unmeasured():
    v = verify_statement(EXAMPLE)
    assert v.claimed == ["efficacy"]
    assert "reachability" in v.rederivable
    assert "efficacy" not in v.rederivable
    assert v.unmeasured == ["interference"]


def test_claimed_rows_are_author_reported_and_labeled_as_such():
    v = verify_statement(EXAMPLE)
    row = next(r for r in v.rows if r.attribute == "efficacy")
    assert row.basis == CLAIMED
    assert row.attribute in v.claimed


def test_tampered_predicate_type_is_not_ok_and_the_error_is_surfaced():
    bad = copy.deepcopy(EXAMPLE)
    bad["predicateType"] = "https://example.com/other/v1"
    v = verify_statement(bad)
    assert v.ok is False
    assert any("attestation/v0.1" in e for e in v.schema_errors)


def test_tampered_missing_input_hash_is_not_ok():
    bad = copy.deepcopy(EXAMPLE)
    del _row(bad, "reachability")["inputHash"]
    v = verify_statement(bad)
    assert v.ok is False
    assert any("inputHash" in e for e in v.schema_errors)


def test_tampered_claimed_to_rederivable_on_efficacy_is_not_ok():
    bad = copy.deepcopy(EXAMPLE)
    r = _row(bad, "efficacy")
    r["basis"] = RE_DERIVABLE
    r["inputHash"] = "sha256:" + "0" * 64
    v = verify_statement(bad)
    assert v.ok is False
    assert v.schema_errors


def test_digest_binding_passes_for_the_real_artifact(tmp_path):
    artifact = tmp_path / "hook.sh"
    artifact.write_text("#!/bin/sh\nexit 0\n")
    stmt = copy.deepcopy(EXAMPLE)
    stmt["subject"][0]["digest"]["sha256"] = digest_path(artifact)

    v = verify_statement(stmt, subject_path=str(artifact))
    assert v.subject_digest_matches is True
    assert v.ok is True


def test_digest_binding_fails_when_a_byte_changes(tmp_path):
    artifact = tmp_path / "hook.sh"
    artifact.write_text("#!/bin/sh\nexit 0\n")
    stmt = copy.deepcopy(EXAMPLE)
    stmt["subject"][0]["digest"]["sha256"] = digest_path(artifact)

    artifact.write_text("#!/bin/sh\nexit 1\n")  # one byte changes downstream
    v = verify_statement(stmt, subject_path=str(artifact))
    assert v.subject_digest_matches is False
    assert v.ok is False, "a digest mismatch is a hard failure: a report for a different artifact"


def test_ok_is_true_only_when_schema_valid_and_digest_matches_or_unchecked(tmp_path):
    artifact = tmp_path / "hook.sh"
    artifact.write_text("x")
    stmt = copy.deepcopy(EXAMPLE)
    stmt["subject"][0]["digest"]["sha256"] = digest_path(artifact)

    assert verify_statement(stmt).ok is True  # no subject given: not checked, so ok
    assert verify_statement(stmt, subject_path=str(artifact)).ok is True

    bad = copy.deepcopy(stmt)
    bad["predicateType"] = "nope"
    assert verify_statement(bad, subject_path=str(artifact)).ok is False


def test_recompute_rows_never_touches_claimed_rows():
    """The recomputer protocol applies to re-derivable rows only; claimed rows are never passed."""
    seen_attributes = []

    class RecordingRecomputer:
        def recompute(self, row, subject_path):  # noqa: ARG002
            seen_attributes.append(row["attribute"])

    recompute_rows(EXAMPLE, "unused-subject-path", [RecordingRecomputer()])

    claimed_names = {
        a["attribute"] for a in EXAMPLE["predicate"]["attributes"] if a["basis"] == CLAIMED
    }
    assert claimed_names, "fixture must have a claimed row for this test to mean anything"
    assert not (set(seen_attributes) & claimed_names)


def test_recompute_rows_uses_first_recomputer_that_can_help():
    class NeverHelps:
        def recompute(self, row, subject_path):  # noqa: ARG002
            return None

    recomputers = [NeverHelps(), InputHashPresenceRecomputer()]
    diffs = recompute_rows(EXAMPLE, "unused-subject-path", recomputers)
    rederivable = [a for a in EXAMPLE["predicate"]["attributes"] if a["basis"] == RE_DERIVABLE]
    assert len(diffs) == len(rederivable)
    assert all(isinstance(d, Diff) for d in diffs)
    assert all(d.matches for d in diffs), "InputHashPresenceRecomputer echoes the row unchanged"


def test_recompute_rows_with_no_helpful_recomputer_yields_no_diffs():
    class NeverHelps:
        def recompute(self, row, subject_path):  # noqa: ARG002
            return None

    assert recompute_rows(EXAMPLE, "unused-subject-path", [NeverHelps()]) == []


def test_input_hash_presence_recomputer_reports_missing_hash():
    row = {"attribute": "reachability", "basis": RE_DERIVABLE, "result": "PASSED"}
    assert InputHashPresenceRecomputer().recompute(row, "unused") is None


def test_diff_flags_a_mismatch_on_result():
    reported = {"attribute": "reachability", "result": "PASSED", "values": {"x": 1}}
    recomputed = {"attribute": "reachability", "result": "FAILED", "values": {"x": 1}}

    class OneShot:
        def recompute(self, row, subject_path):  # noqa: ARG002
            return recomputed

    reported_row = {**reported, "basis": RE_DERIVABLE, "inputHash": "sha256:" + "0" * 64}
    stmt = {"predicate": {"attributes": [reported_row]}}
    diffs = recompute_rows(stmt, "unused", [OneShot()])
    assert len(diffs) == 1
    assert diffs[0].matches is False


def test_measurement_diff_ignores_the_actual_numbers_but_not_the_unit():
    """Environment-sensitive measurements may differ run to run (spec's OPEN QUESTION)."""
    reported = {
        "attribute": "cost.latency_ms",
        "basis": RE_DERIVABLE,
        "result": "PASSED",
        "inputHash": "sha256:" + "0" * 64,
        "measurement": {"unit": "ms", "n": 200, "mean": 151},
    }
    recomputed_same_unit = {
        "attribute": "cost.latency_ms",
        "result": "PASSED",
        "measurement": {"unit": "ms", "n": 5, "mean": 9999},
    }
    recomputed_diff_unit = {
        "attribute": "cost.latency_ms",
        "result": "PASSED",
        "measurement": {"unit": "seconds", "n": 5, "mean": 9999},
    }

    class Fixed:
        def __init__(self, out):
            self.out = out

        def recompute(self, row, subject_path):  # noqa: ARG002
            return self.out

    stmt = {"predicate": {"attributes": [reported]}}
    assert recompute_rows(stmt, "unused", [Fixed(recomputed_same_unit)])[0].matches is True
    assert recompute_rows(stmt, "unused", [Fixed(recomputed_diff_unit)])[0].matches is False


def test_to_svr_has_the_required_svr_v02_fields_and_no_slsa_prefix():
    v = verify_statement(EXAMPLE)
    svr = to_svr(
        v,
        verifier_id="https://example.com/verifier",
        report_digest_sha256="a" * 64,
        policy_uri="https://example.com/policy",
    )

    assert svr["_type"] == "https://in-toto.io/Statement/v1"
    assert svr["predicateType"] == "https://in-toto.io/attestation/svr/v0.2"
    assert svr["subject"] == [{"digest": {"sha256": "a" * 64}}]

    predicate = svr["predicate"]
    assert set(predicate) == {"verifier", "timeCreated", "properties"}
    assert predicate["verifier"] == {
        "id": "https://example.com/verifier",
        "policies": [{"uri": "https://example.com/policy"}],
    }
    assert predicate["timeCreated"].endswith("Z")
    assert "CONTEXT_REPORT_WELL_FORMED" in predicate["properties"]
    assert "CONTEXT_REPORT_SUBJECT_BOUND" not in predicate["properties"]  # no subject_path checked
    assert "CONTEXT_REPORT_CLAIMED_ROWS:1" in predicate["properties"]
    assert not any(p.startswith("SLSA_") for p in predicate["properties"])
    assert json.dumps(svr)  # serialisable


def test_to_svr_marks_subject_bound_only_when_digest_was_actually_checked(tmp_path):
    artifact = tmp_path / "hook.sh"
    artifact.write_text("x")
    stmt = copy.deepcopy(EXAMPLE)
    stmt["subject"][0]["digest"]["sha256"] = digest_path(artifact)

    v = verify_statement(stmt, subject_path=str(artifact))
    svr = to_svr(v, verifier_id="https://example.com/v", report_digest_sha256="b" * 64)
    assert "CONTEXT_REPORT_SUBJECT_BOUND" in svr["predicate"]["properties"]
    assert svr["predicate"]["verifier"]["policies"] == []


def test_to_svr_omits_well_formed_when_schema_invalid():
    bad = copy.deepcopy(EXAMPLE)
    bad["predicateType"] = "nope"
    v = verify_statement(bad)
    svr = to_svr(v, verifier_id="https://example.com/v", report_digest_sha256="c" * 64)
    assert "CONTEXT_REPORT_WELL_FORMED" not in svr["predicate"]["properties"]


def test_verification_is_a_frozen_dataclass():
    v = verify_statement(EXAMPLE)
    assert isinstance(v, Verification)
    with pytest.raises(AttributeError):
        v.ok = False  # type: ignore[misc]
