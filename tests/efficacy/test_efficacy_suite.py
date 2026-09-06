"""Measuring many rules on the same task issues the control generation only once."""

from context_report.efficacy import RuleCard, Scenario
from context_report.efficacy.suite import measure_suite

SHARED_TASK = "write is_valid(user)"


class CountingRunner:
    def __init__(self):
        self.calls = 0

    def run(self, task, rule):
        self.calls += 1
        return "OBEY" if rule is not None else "BASE"


class MarkerJudge:
    def obeys(self, rule, task, output, criterion):
        return output == "OBEY"


def _rule(rid):
    return RuleCard(rid, f"text-{rid}", (Scenario("s", SHARED_TASK, "applies"),))


def test_control_arm_is_shared_across_rules():
    inner = CountingRunner()
    rules = [_rule("a"), _rule("b"), _rule("c")]
    res = measure_suite(rules, inner, MarkerJudge())
    assert res.runner_calls == 4
    assert res.naive_runner_calls == 6
    assert inner.calls == 4


def test_reports_cover_every_rule():
    res = measure_suite([_rule("a"), _rule("b")], CountingRunner(), MarkerJudge())
    assert {r.rule_id for r in res.reports} == {"a", "b"}
    for r in res.reports:
        assert r.adherence_with == 1.0 and r.adherence_without == 0.0


def test_savings_grow_with_more_rules_on_one_task():
    inner = CountingRunner()
    rules = [_rule(str(i)) for i in range(10)]
    res = measure_suite(rules, inner, MarkerJudge())
    assert res.runner_calls == 11
    assert res.naive_runner_calls == 20
