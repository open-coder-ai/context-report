"""Templates live in data files: every token the code supplies exists, and none is left behind."""

import pytest

from context_report.efficacy import prompts

SUPPLIED = {
    "judge": {"rule": "r", "task": "t", "output": "o", "criterion": "c"},
    "run_with_rule": {"rule": "r", "task": "t"},
    "scenarios": {"rule": "r", "count": "3"},
}


@pytest.mark.parametrize("name", sorted(SUPPLIED))
def test_every_token_is_supplied_and_none_is_orphaned(name):
    expected = {f"__{key.upper()}__" for key in SUPPLIED[name]}
    assert prompts.tokens_in(name) == expected


@pytest.mark.parametrize("name", sorted(SUPPLIED))
def test_render_leaves_no_placeholder(name):
    text = prompts.render(name, **SUPPLIED[name])
    assert "__" not in text


def test_unknown_token_is_an_error():
    with pytest.raises(KeyError):
        prompts.render("judge", rule="r", task="t", output="o", extra="x")


def test_missing_token_is_an_error():
    with pytest.raises(KeyError):
        prompts.render("judge", rule="r")


def test_judged_output_is_placed_after_the_rule_and_task():
    template = prompts.template("judge")
    assert template.index("__RULE__") < template.index("__TASK__") < template.index("__OUTPUT__")


def test_scenario_prompt_forbids_leaking_the_rule_into_the_task():
    text = prompts.render("scenarios", rule="use tabs", count="2")
    assert "must not" in text
    assert "the rule away" in text
