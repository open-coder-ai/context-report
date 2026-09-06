"""Scenario building: parse what the model returns, refuse to measure a rule with no scenarios."""

import json

import pytest

from context_report.efficacy import scenarios
from context_report.efficacy.rules import Rule

RULE = Rule(id="CLAUDE.md:3", text="never use field injection", source="CLAUDE.md", line=3)


class ReplyAsker:
    def __init__(self, reply):
        self.reply = reply
        self.prompts = []

    def ask(self, prompt):
        self.prompts.append(prompt)
        return self.reply


def test_parse_tasks_reads_a_bare_array():
    assert scenarios.parse_tasks('["a", "b"]') == ["a", "b"]


def test_parse_tasks_survives_chatty_output():
    assert scenarios.parse_tasks('Sure!\n["a", "b"]\nHope that helps') == ["a", "b"]


def test_parse_tasks_rejects_non_arrays():
    with pytest.raises(ValueError):
        scenarios.parse_tasks("I could not think of any.")


def test_generate_asks_with_the_rule_and_caps_the_count():
    asker = ReplyAsker(json.dumps(["one", "two", "three"]))
    tasks = scenarios.generate(RULE, asker, count=2)
    assert tasks == ["one", "two"]
    assert RULE.text in asker.prompts[0]


def test_card_pairs_rule_with_scenarios():
    card = scenarios.card(RULE, ["write a service", "add a controller"])
    assert card.id == RULE.id
    assert [s.task for s in card.scenarios] == ["write a service", "add a controller"]
    assert card.scenarios[0].id == "CLAUDE.md:3#0"


def test_card_refuses_an_empty_scenario_list():
    with pytest.raises(ValueError):
        scenarios.card(RULE, [])


def test_load_reads_hand_written_scenarios(tmp_path):
    path = tmp_path / "scenarios.json"
    path.write_text(json.dumps({"CLAUDE.md:3": ["task one"]}), encoding="utf-8")
    assert scenarios.load(path) == {"CLAUDE.md:3": ["task one"]}
