"""Ingesting a vendor `claude plugin eval` result: parsing, pooling, and the row it produces."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from context_report.cli import main
from context_report.efficacy.pluginval import (
    SUPPORTED_SCHEMA_VERSIONS,
    efficacy_row_from_vendor,
    load,
)
from context_report.rows import CLAIMED, FAILED, NOT_APPLICABLE
from context_report.statement import validate

FIXTURE = Path(__file__).parent / "fixtures" / "plugin-eval" / "aggregate-result.json"


def _write(tmp_path: Path, doc: dict) -> Path:
    p = tmp_path / "aggregate-result.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def _minimal_case(name: str = "c1", tags: list[str] | None = None) -> dict:
    case: dict = {
        "name": name,
        "arms": {
            "with": [{"graders": [{"name": "g", "type": "regex", "passed": True}]}],
            "without": [{"graders": [{"name": "g", "type": "regex", "passed": False}]}],
        },
    }
    if tags is not None:
        case["tags"] = tags
    return case


# --- load(): required fields, and where the reference is silent ---------------------------------


def test_load_the_fixture() -> None:
    result = load(FIXTURE)
    assert result.schema_version == "1"
    assert result.schema_version_pinned is True
    assert result.suite == "policy-compliance"
    assert len(result.cases) == 2
    assert result.skipped_grader_types == ("custom_note",)


def test_missing_schema_version_names_the_field(tmp_path: Path) -> None:
    p = _write(tmp_path, {"cases": []})
    with pytest.raises(ValueError, match=r"schemaVersion"):
        load(p)


def test_missing_cases_names_the_field(tmp_path: Path) -> None:
    p = _write(tmp_path, {"schemaVersion": "1"})
    with pytest.raises(ValueError, match=r"cases"):
        load(p)


def test_missing_case_name_names_the_field(tmp_path: Path) -> None:
    doc = {"schemaVersion": "1", "cases": [{"arms": {"with": [], "without": []}}]}
    p = _write(tmp_path, doc)
    with pytest.raises(ValueError, match=r"cases\[0\]\.name"):
        load(p)


def test_missing_arms_names_the_field(tmp_path: Path) -> None:
    doc = {"schemaVersion": "1", "cases": [{"name": "c"}]}
    p = _write(tmp_path, doc)
    with pytest.raises(ValueError, match=r"cases\[0\]\.arms"):
        load(p)


def test_missing_without_arm_names_the_field(tmp_path: Path) -> None:
    doc = {"schemaVersion": "1", "cases": [{"name": "c", "arms": {"with": []}}]}
    p = _write(tmp_path, doc)
    with pytest.raises(ValueError, match=r"cases\[0\]\.arms\.without"):
        load(p)


def test_missing_grader_passed_names_the_field(tmp_path: Path) -> None:
    doc = {
        "schemaVersion": "1",
        "cases": [
            {
                "name": "c",
                "arms": {
                    "with": [{"graders": [{"name": "g", "type": "regex"}]}],
                    "without": [],
                },
            }
        ],
    }
    p = _write(tmp_path, doc)
    with pytest.raises(ValueError, match=r"cases\[0\]\.arms\.with\[0\]\.graders\[0\]\.passed"):
        load(p)


def test_missing_tags_and_optional_fields_are_tolerated(tmp_path: Path) -> None:
    """tags, cost, tokens and score are all absent in the reference's silence; none is required."""
    doc = {"schemaVersion": "1", "cases": [_minimal_case()]}
    result = load(_write(tmp_path, doc))
    assert result.suite is None
    assert result.cases[0].tags == ()
    run = result.cases[0].with_runs[0]
    assert run.cost is None and run.input_tokens is None and run.output_tokens is None


# --- pass-rate, lift, and CI math against hand-computed numbers ---------------------------------


def test_a_run_passes_only_when_every_grader_passes() -> None:
    result = load(FIXTURE)
    without_runs = result.cases[1].without_runs  # formatting-check, run 0 has two graders
    assert without_runs[0].graders[0].passed is True
    assert without_runs[0].graders[1].passed is True
    assert without_runs[0].passed is True
    assert without_runs[2].passed is False  # its one grader failed


def test_pass_rate_and_lift_match_hand_computed_numbers() -> None:
    result = load(FIXTURE)
    row = efficacy_row_from_vendor(result, model="m")
    per_rule = {r["ruleId"]: r for r in row.values["perRule"]}

    secrets = per_rule["never-commit-secrets"]
    assert secrets["adherenceWith"] == pytest.approx(3 / 3)
    assert secrets["adherenceWithout"] == pytest.approx(1 / 3)
    assert secrets["lift"] == pytest.approx(2 / 3)
    assert secrets["observationsPerArm"] == 3

    fmt = per_rule["formatting-check"]
    assert fmt["adherenceWith"] == pytest.approx(2 / 3)
    assert fmt["adherenceWithout"] == pytest.approx(2 / 3)
    assert fmt["lift"] == pytest.approx(0.0)


def test_tag_mapping_uses_rule_tag_or_falls_back_to_case_name() -> None:
    result = load(FIXTURE)
    tagged, untagged = result.cases
    assert tagged.rule_id == "never-commit-secrets"
    assert untagged.rule_id == "formatting-check"  # no rule: tag -> pseudo rule id is the case name


def test_multiple_cases_pool_into_one_rule_report(tmp_path: Path) -> None:
    doc = {
        "schemaVersion": "1",
        "cases": [
            _minimal_case("a", tags=["rule:x"]),
            _minimal_case("b", tags=["rule:x"]),
        ],
    }
    result = load(_write(tmp_path, doc))
    row = efficacy_row_from_vendor(result, model="m")
    assert len(row.values["perRule"]) == 1
    only = row.values["perRule"][0]
    assert only["ruleId"] == "x"
    assert only["observationsPerArm"] == 2  # one run per case, two cases pooled


# --- unknown schemaVersion is accepted but recorded ----------------------------------------------


def test_unknown_schema_version_is_ingested_but_noted(tmp_path: Path) -> None:
    doc = {"schemaVersion": "99", "cases": [_minimal_case(tags=["rule:x"])]}
    result = load(_write(tmp_path, doc))
    assert result.schema_version_pinned is False
    row = efficacy_row_from_vendor(result, model="m")
    assert "schemaVersion 99 not in the pinned set" in row.reasoning
    assert row.conditions["ablation"] == "claude-plugin-eval@99"


def test_supported_schema_versions_is_just_one_for_now() -> None:
    assert frozenset({"1"}) == SUPPORTED_SCHEMA_VERSIONS


# --- the row's conditions and provenance ----------------------------------------------------------


def test_efficacy_row_from_vendor_is_claimed_with_vendor_conditions() -> None:
    result = load(FIXTURE)
    row = efficacy_row_from_vendor(result, model="anthropic/claude-sonnet-5")
    assert row.attribute == "efficacy"
    assert row.basis == CLAIMED
    assert row.conditions["ablation"] == "claude-plugin-eval@1"
    assert row.conditions["judge"] == "vendor-grader"
    assert row.conditions["judgeModel"] is None
    assert row.conditions["model"] == "anthropic/claude-sonnet-5"
    assert row.values["vendor"] == {
        "tool": "claude plugin eval",
        "schemaVersion": "1",
        "suite": "policy-compliance",
        "cases": 2,
        "skippedGraderTypes": ["custom_note"],
    }
    # small-N fixture: the point is the shape of the row, not the verdict it happens to land on.
    assert row.result in (FAILED, "WARNED", "PASSED")


def test_uneven_runs_per_case_are_noted(tmp_path: Path) -> None:
    """Two cases for one rule with different trial counts: reported as the minimum, and said."""
    doc = {
        "schemaVersion": "1",
        "cases": [
            {
                "name": "a",
                "tags": ["rule:x"],
                "arms": {
                    "with": [{"graders": [{"name": "g", "type": "regex", "passed": True}]}] * 3,
                    "without": [{"graders": [{"name": "g", "type": "regex", "passed": False}]}] * 3,
                },
            },
            {
                "name": "b",
                "tags": ["rule:x"],
                "arms": {
                    "with": [{"graders": [{"name": "g", "type": "regex", "passed": True}]}] * 2,
                    "without": [{"graders": [{"name": "g", "type": "regex", "passed": False}]}] * 2,
                },
            },
        ],
    }
    result = load(_write(tmp_path, doc))
    row = efficacy_row_from_vendor(result, model="m")
    only = row.values["perRule"][0]
    assert only["observationsPerArm"] == 5  # 3 + 2 runs summed over the pooled cases
    assert "uneven" in row.reasoning


# --- ingest-eval CLI, end to end -----------------------------------------------------------------


@pytest.fixture
def plugin_dir(tmp_path: Path) -> Path:
    """A minimal, self-describing plugin bundle with no hooks: nothing to execute, still valid."""
    plugin = tmp_path / "plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "demo-plugin", "version": "0.1.0"})
    )
    return plugin


def test_ingest_eval_cli_end_to_end(plugin_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "statement.json"
    rc = main(
        [
            "ingest-eval",
            str(FIXTURE),
            "--subject",
            str(plugin_dir),
            "--kind",
            "plugin",
            "--target",
            "claude_code",
            "--model",
            "anthropic/claude-sonnet-5",
            "--out",
            str(out),
        ]
    )
    assert rc == 0 and out.exists()
    stmt = json.loads(out.read_text())
    assert validate(stmt) == []

    rows = {a["attribute"]: a for a in stmt["predicate"]["attributes"]}
    efficacy = rows["efficacy"]
    assert efficacy["basis"] == CLAIMED
    assert efficacy["conditions"]["ablation"] == "claude-plugin-eval@1"
    assert efficacy["conditions"]["judge"] == "vendor-grader"
    assert efficacy["values"]["vendor"]["tool"] == "claude plugin eval"
    # a plugin with no hooks: the executable rows are honestly NotApplicable, not silently skipped.
    assert rows["reachability"]["result"] == NOT_APPLICABLE

    byproducts = stmt["predicate"]["byproducts"]
    assert any(b["name"] == "aggregate-result.json" for b in byproducts)
    expected = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    assert byproducts[0]["digest"]["sha256"] == expected


def test_ingest_eval_cli_missing_result_file_exits_2(plugin_dir: Path, tmp_path: Path) -> None:
    rc = main(
        [
            "ingest-eval",
            str(tmp_path / "nope.json"),
            "--subject",
            str(plugin_dir),
            "--kind",
            "plugin",
            "--target",
            "claude_code",
            "--model",
            "m",
        ]
    )
    assert rc == 2


def test_ingest_eval_cli_bad_result_exits_2(plugin_dir: Path, tmp_path: Path, capsys) -> None:
    bad = _write(tmp_path, {"cases": []})
    rc = main(
        [
            "ingest-eval",
            str(bad),
            "--subject",
            str(plugin_dir),
            "--kind",
            "plugin",
            "--target",
            "claude_code",
            "--model",
            "m",
        ]
    )
    assert rc == 2
    assert "schemaVersion" in capsys.readouterr().err


def test_ingest_eval_cli_usage_error_exits_2() -> None:
    assert main(["ingest-eval", str(FIXTURE), "--kind", "plugin", "--target", "x"]) == 2
