"""Grading never guesses, and the efficacy row is always claimed and always explains itself."""

from __future__ import annotations

from context_report.efficacy import grade as g
from context_report.efficacy.core import RuleCard, Scenario
from context_report.efficacy.fastjudge import CannotJudgeError
from context_report.efficacy.row import ABLATION_PROMPT_PREFIX, efficacy_row
from context_report.rows import CLAIMED, FAILED, NOT_AVAILABLE, PASSED, WARNED

GRADABLE = RuleCard(
    "a", "Rule A.", tuple(Scenario(f"t{i}", f"task {i}", "Rule A.") for i in range(8))
)
PROSE = RuleCard("b", "Explain first.", (Scenario("t1", "task", "Explain first."),))


class ObeysWithRule:
    def run(self, task: str, rule: str | None) -> str:
        return "obeyed" if rule else "ignored"


class CodeJudge:
    """Grades rule A by its output; refuses rule B like a judge with no model would."""

    def obeys(self, rule: str, task: str, output: str, criterion: str) -> bool:
        if rule == "Explain first.":
            raise CannotJudgeError("prose")
        return output == "obeyed"


def test_grade_reports_gradable_rules_and_names_the_rest() -> None:
    graded = g.grade([GRADABLE, PROSE], ObeysWithRule(), CodeJudge(), trials=3)
    assert [r.rule_id for r in graded.reports] == ["a"]
    assert graded.ungraded == ("b",)
    assert graded.judge == g.JUDGE_MODEL  # a judge object was supplied, even if it refused one rule


def test_no_judge_means_deterministic_only() -> None:
    graded = g.grade([PROSE], ObeysWithRule(), None, trials=1)
    assert graded.reports == () and graded.ungraded == ("b",)
    assert graded.judge == g.JUDGE_DETERMINISTIC


def test_row_with_clear_lift_passes_and_carries_conditions() -> None:
    graded = g.grade([GRADABLE, PROSE], ObeysWithRule(), CodeJudge(), trials=3)
    row = efficacy_row(
        graded,
        model="anthropic/claude-sonnet-5",
        judge_model="anthropic/claude-opus-5",
        measured_on="2026-09-06",
        n_per_arm=3,
        tokens_per_arm={"inputTokens": 10, "outputTokens": 20},
        transcripts=48,
    )
    assert row.basis == CLAIMED and row.result == PASSED
    assert row.estimate.point_estimate == 1.0 and row.estimate.lower_bound > 0
    assert row.conditions["ablation"] == ABLATION_PROMPT_PREFIX
    assert row.conditions["judgeModel"] == "anthropic/claude-opus-5"
    assert row.values["perRule"][0]["ruleId"] == "a" and row.values["ungraded"] == ["b"]
    assert row.values["tokensPerArm"] == {"inputTokens": 10, "outputTokens": 20}
    assert "b" in row.reasoning


def test_row_with_nothing_graded_is_not_available_and_says_what_was_recorded() -> None:
    graded = g.grade([PROSE], ObeysWithRule(), None, trials=2)
    row = efficacy_row(
        graded, model="m", judge_model=None, measured_on="d", n_per_arm=2, transcripts=4
    )
    assert row.result == NOT_AVAILABLE and row.basis == CLAIMED and row.estimate is None
    assert "4 paired transcripts" in row.reasoning and "no judge model" in row.reasoning
    assert row.conditions["judge"] == g.JUDGE_DETERMINISTIC


def test_row_with_no_effect_fails_and_a_wide_interval_warns() -> None:
    class Same:
        def run(self, task: str, rule: str | None) -> str:
            return "obeyed"

    class Yes:
        def obeys(self, rule: str, task: str, output: str, criterion: str) -> bool:
            return True

    graded = g.grade([GRADABLE], Same(), Yes(), trials=1)
    assert (
        efficacy_row(graded, model="m", judge_model="j", measured_on="d", n_per_arm=1).result
        == FAILED
    )

    tiny = RuleCard("a", "Rule A.", (Scenario("t0", "task", "Rule A."),))
    graded = g.grade([tiny], ObeysWithRule(), CodeJudge(), trials=1)
    row = efficacy_row(graded, model="m", judge_model="j", measured_on="d", n_per_arm=1)
    assert row.result in (WARNED, FAILED), "one observation per arm cannot support PASSED"
