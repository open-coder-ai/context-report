"""Cards bind a subject's own rules to the tasks that exercise them; nothing else."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from context_report.run import manifest as m
from context_report.run.cards import cards_for, unexercised_rules
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
