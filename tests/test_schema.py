"""The v0.1 schema accepts the example and rejects the shapes the spec forbids."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
V01 = ROOT / "spec" / "attestation" / "v0.1"
SCHEMA = json.loads((V01 / "schema.json").read_text(encoding="utf-8"))
EXAMPLE = json.loads((V01 / "examples" / "plugin-copilot.json").read_text(encoding="utf-8"))

validator = Draft202012Validator(SCHEMA)


def errors(instance: dict) -> list[str]:
    return [e.message for e in validator.iter_errors(instance)]


def row(instance: dict, name: str) -> dict:
    return next(a for a in instance["predicate"]["attributes"] if a["attribute"] == name)


def test_schema_is_itself_valid() -> None:
    Draft202012Validator.check_schema(SCHEMA)


def test_example_validates() -> None:
    assert errors(EXAMPLE) == []


def test_example_covers_every_v01_attribute_family() -> None:
    """The example is the spec's worked case; a family missing from it is a family nobody has tried."""
    names = {a["attribute"].split(".")[0] for a in EXAMPLE["predicate"]["attributes"]}
    assert {"reachability", "fault", "cost", "interference", "efficacy"} <= names


def test_rederivable_row_without_inputhash_is_rejected() -> None:
    """re-derivable is checkable only because of inputHash; without it the word is an assertion."""
    bad = copy.deepcopy(EXAMPLE)
    del row(bad, "reachability")["inputHash"]
    assert any("inputHash" in e for e in errors(bad))


def test_unmeasured_row_must_say_why() -> None:
    """Monotonic principle: an unmeasured row may never be read as a pass, and must explain itself."""
    bad = copy.deepcopy(EXAMPLE)
    del row(bad, "interference")["reasoning"]
    assert any("reasoning" in e for e in errors(bad))


def test_efficacy_may_never_be_rederivable() -> None:
    bad = copy.deepcopy(EXAMPLE)
    r = row(bad, "efficacy")
    r["basis"] = "re-derivable"
    r["inputHash"] = "sha256:" + "0" * 64
    assert errors(bad), "efficacy is stochastic by construction"


def test_result_is_required_on_every_row() -> None:
    """A row with a measurement but no result would let a consumer infer a pass. It must not."""
    bad = copy.deepcopy(EXAMPLE)
    del row(bad, "cost.latency_ms")["result"]
    assert any("result" in e for e in errors(bad))


def test_unknown_attribute_needs_x_prefix() -> None:
    bad = copy.deepcopy(EXAMPLE)
    row(bad, "reachability")["attribute"] = "vibes"
    assert errors(bad)
    ok = copy.deepcopy(EXAMPLE)
    row(ok, "reachability")["attribute"] = "x-vibes"
    assert errors(ok) == []


def test_predicate_type_is_pinned() -> None:
    bad = copy.deepcopy(EXAMPLE)
    bad["predicateType"] = "https://example.com/other/v1"
    assert errors(bad)


def test_subject_requires_a_digest() -> None:
    """in-toto: subjects match purely by digest. A subject with only a name binds to nothing."""
    bad = copy.deepcopy(EXAMPLE)
    bad["subject"] = [{"name": "my-plugin"}]
    assert errors(bad)


@pytest.mark.parametrize("kind", ["plugin", "instruction-file", "skill", "hook", "mcp-server", "subagent"])
def test_every_subject_kind_is_accepted(kind: str) -> None:
    ok = copy.deepcopy(EXAMPLE)
    ok["predicate"]["subjectKind"] = kind
    assert errors(ok) == []


def test_percentile_keys_are_percentiles() -> None:
    bad = copy.deepcopy(EXAMPLE)
    row(bad, "cost.latency_ms")["measurement"]["percentiles"] = {"p50": 143}
    assert errors(bad)
