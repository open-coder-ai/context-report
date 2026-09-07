"""The v0.1 schema accepts the example and rejects the shapes the spec forbids."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from context_report.statement import validate

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
    """The example is the spec's worked case; a family missing from it is one nobody has tried."""
    names = {a["attribute"].split(".")[0] for a in EXAMPLE["predicate"]["attributes"]}
    assert {"reachability", "fault", "cost", "interference", "efficacy"} <= names


def test_rederivable_row_without_inputhash_is_rejected() -> None:
    """re-derivable is checkable only because of inputHash; without it the word is an assertion."""
    bad = copy.deepcopy(EXAMPLE)
    del row(bad, "reachability")["inputHash"]
    assert any("inputHash" in e for e in errors(bad))


def test_unmeasured_row_must_say_why() -> None:
    """Monotonic principle: an unmeasured row is never a pass, and must explain itself."""
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


KINDS = ["plugin", "instruction-file", "skill", "hook", "mcp-server", "subagent"]
APPLICABILITY = json.loads(
    (ROOT / "src" / "context_report" / "data" / "applicability-v0.1.json").read_text(
        encoding="utf-8"
    )
)["notApplicable"]


def _not_applicable(r: dict, kind: str) -> None:
    for key in ("measurement", "estimate", "conditions", "values", "environment"):
        r.pop(key, None)
    r["result"] = "NotApplicable"
    r["reasoning"] = f"{r['attribute']} does not apply to subjectKind {kind}"


@pytest.mark.parametrize("kind", KINDS)
def test_every_subject_kind_is_accepted(kind: str) -> None:
    """The example re-kinded validates once the rows the registry excludes are NotApplicable."""
    ok = copy.deepcopy(EXAMPLE)
    ok["predicate"]["subjectKind"] = kind
    for r in ok["predicate"]["attributes"]:
        if r["attribute"] in APPLICABILITY[kind]:
            _not_applicable(r, kind)
    assert errors(ok) == []


def test_percentile_keys_are_percentiles() -> None:
    bad = copy.deepcopy(EXAMPLE)
    row(bad, "cost.latency_ms")["measurement"]["percentiles"] = {"p50": 143}
    assert errors(bad)


def test_measured_latency_must_record_its_environment() -> None:
    bad = copy.deepcopy(EXAMPLE)
    del row(bad, "cost.latency_ms")["environment"]
    assert errors(bad), "a measured latency without its runner is not re-derivable to anything"
    bad = copy.deepcopy(EXAMPLE)
    row(bad, "cost.latency_ms")["environmentSensitive"] = False
    assert errors(bad), "latency is environmentSensitive by definition"


def test_const_mismatch_names_the_path_and_the_expected_and_actual_values() -> None:
    """A const failure (here: the cost.latency_ms row's environmentSensitive) names both sides."""
    bad = copy.deepcopy(EXAMPLE)
    idx, r = next(
        (i, a)
        for i, a in enumerate(bad["predicate"]["attributes"])
        if a["attribute"] == "cost.latency_ms"
    )
    r["environmentSensitive"] = False
    errs = validate(bad)
    assert any(
        e == f"predicate/attributes/{idx}/environmentSensitive: expected True, got False"
        for e in errs
    )


def test_nested_if_then_failure_under_a_subject_kind_block_is_path_prefixed() -> None:
    """An instruction-file's cost.latency_ms row must be NotApplicable; the path names the row."""
    bad = copy.deepcopy(EXAMPLE)
    bad["predicate"]["subjectKind"] = "instruction-file"
    idx = next(
        i
        for i, a in enumerate(bad["predicate"]["attributes"])
        if a["attribute"] == "cost.latency_ms"
    )
    errs = validate(bad)
    assert any(
        e == f"predicate/attributes/{idx}/result: expected 'NotApplicable', got 'PASSED'"
        for e in errs
    )


def test_root_level_error_keeps_a_stable_non_empty_prefix() -> None:
    """A missing top-level field has no JSON path segment of its own; it still gets a prefix."""
    bad = copy.deepcopy(EXAMPLE)
    del bad["_type"]
    errs = validate(bad)
    assert any(e.startswith("(root): ") and "_type" in e for e in errs)


def test_attribute_that_does_not_apply_to_the_kind_must_be_not_applicable() -> None:
    """A hook script is not injected into context, so cost.context_tokens cannot PASS for a hook."""
    bad = copy.deepcopy(EXAMPLE)
    bad["predicate"]["subjectKind"] = "hook"
    assert errors(bad), "PASSED context_tokens and efficacy rows on a hook must be rejected"
    ok = copy.deepcopy(bad)
    for name in ("cost.context_tokens", "efficacy"):
        r = row(ok, name)
        for key in ("measurement", "estimate", "conditions", "values"):
            r.pop(key, None)
        r["result"] = "NotApplicable"
        r["reasoning"] = f"{name} does not apply to subjectKind hook"
    assert errors(ok) == []
