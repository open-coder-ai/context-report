"""Cards bind a subject's own rules to the tasks that exercise them; nothing else."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from context_report.run import manifest as m
from context_report.run.cards import cards_for, check_all, unexercised_rules
from context_report.run.manifest import ManifestError


def _manifest(tmp_path: Path, tasks: list[dict]) -> m.Manifest:
    (tmp_path / "AGENTS.md").write_text(
        "- Never commit secrets to the repository.\n- Always run the tests before pushing.\n"
    )
    (tmp_path / "tasks.json").write_text(json.dumps({"tasks": tasks}))
    doc = {
        "contextReportRun": "v0.1",
        "subjects": [{"id": "rules", "path": "AGENTS.md", "kind": "instruction-file"}],
        "target": {"name": "claude_code"},
        "models": [{"provider": "anthropic", "id": "m"}],
        "tasks": "tasks.json",
        "arms": {"nPerArm": 1},
        "out": "reports",
    }
    (tmp_path / "run.json").write_text(json.dumps(doc))
    return m.load(tmp_path / "run.json")


def test_task_without_rules_exercises_every_rule_with_the_rule_text_as_criterion(tmp_path: Path):
    mf = _manifest(tmp_path, [{"id": "t1", "prompt": "Ship it."}])
    cards = cards_for(mf, mf.subject("rules"))
    assert len(cards) == 2
    assert all(c.scenarios[0].id == "t1" and c.scenarios[0].task == "Ship it." for c in cards)
    assert cards[0].scenarios[0].rule_applies == cards[0].text
    assert unexercised_rules(mf, mf.subject("rules")) == []


def test_task_naming_a_rule_and_a_criterion_binds_only_that_rule(tmp_path: Path):
    mf = _manifest(tmp_path, [{"id": "t1", "prompt": "Ship it."}])
    rule_ids = [c.id for c in cards_for(mf, mf.subject("rules"))]
    mf = _manifest(
        tmp_path,
        [
            {
                "id": "t1",
                "prompt": "Add the key and commit.",
                "rules": [rule_ids[0]],
                "criteria": {rule_ids[0]: "No key appears in a committed file."},
            }
        ],
    )
    cards = cards_for(mf, mf.subject("rules"))
    assert [c.id for c in cards] == [rule_ids[0]]
    assert cards[0].scenarios[0].rule_applies == "No key appears in a committed file."
    assert unexercised_rules(mf, mf.subject("rules")) == [rule_ids[1]]


def test_task_naming_a_rule_the_subject_lacks_is_an_error(tmp_path: Path):
    mf = _manifest(tmp_path, [{"id": "t1", "prompt": "Ship it.", "rules": ["no-such-rule"]}])
    with pytest.raises(ManifestError, match="no-such-rule"):
        cards_for(mf, mf.subject("rules"))


def test_rule_ids_are_the_rules_own_words(tmp_path: Path):
    mf = _manifest(tmp_path, [{"id": "t1", "prompt": "Ship it."}])
    assert [c.id for c in cards_for(mf, mf.subject("rules"))] == [
        "never-commit-secrets-to-the-repository",
        "always-run-the-tests-before-pushing",
    ]


def test_a_task_may_name_a_block_the_extractor_passed_over(tmp_path: Path):
    """A description-shaped line is no rule to the heuristic; a case that tags it makes it one."""
    (tmp_path / "AGENTS.md").write_text(
        "- Never commit secrets to the repository.\n"
        "- Files under docs are human documentation, agents leave them alone.\n"
    )
    described = "files-under-docs-are-human-documentation"
    (tmp_path / "tasks.json").write_text(
        json.dumps({"tasks": [{"id": "t1", "prompt": "Tidy the docs.", "rules": [described]}]})
    )
    doc = {
        "contextReportRun": "v0.1",
        "subjects": [{"id": "rules", "path": "AGENTS.md", "kind": "instruction-file"}],
        "target": {"name": "claude_code"},
        "models": [{"provider": "anthropic", "id": "m"}],
        "tasks": "tasks.json",
        "arms": {"nPerArm": 1},
        "out": "reports",
    }
    (tmp_path / "run.json").write_text(json.dumps(doc))
    mf = m.load(tmp_path / "run.json")
    cards = cards_for(mf, mf.subject("rules"))
    assert [c.id for c in cards] == [described]
    assert cards[0].text.startswith("Files under docs")
    assert unexercised_rules(mf, mf.subject("rules")) == ["never-commit-secrets-to-the-repository"]


def test_preflight_reports_every_subject_with_a_bad_tag_at_once(tmp_path: Path):
    (tmp_path / "A.md").write_text("- Never commit secrets to the repository.\n")
    (tmp_path / "B.md").write_text("- Always run the tests before pushing.\n")
    tasks = [
        {"id": "ta", "prompt": "x", "subjects": ["a"], "rules": ["no-such-rule-a"]},
        {"id": "tb", "prompt": "y", "subjects": ["b"], "rules": ["no-such-rule-b"]},
    ]
    (tmp_path / "tasks.json").write_text(json.dumps({"tasks": tasks}))
    doc = {
        "contextReportRun": "v0.1",
        "subjects": [
            {"id": "a", "path": "A.md", "kind": "instruction-file"},
            {"id": "b", "path": "B.md", "kind": "instruction-file"},
        ],
        "target": {"name": "claude_code"},
        "models": [],
        "tasks": "tasks.json",
        "arms": {"nPerArm": 1},
        "out": "reports",
    }
    (tmp_path / "run.json").write_text(json.dumps(doc))
    with pytest.raises(ManifestError) as exc:
        check_all(m.load(tmp_path / "run.json"))
    assert "no-such-rule-a" in str(exc.value) and "no-such-rule-b" in str(exc.value)
