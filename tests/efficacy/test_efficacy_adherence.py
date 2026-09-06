"""The engine is pure: with a deterministic mock model, the lift math and verdicts are exact."""

import pytest

from context_report.efficacy import RuleCard, Scenario, format_report, measure


class TableRunner:
    """Mock model. table: task -> (obeys_when_rule_present, obeys_when_rule_absent)."""

    def __init__(self, table):
        self.table = table

    def run(self, task, rule):
        with_b, without_b = self.table[task]
        obeys = with_b if rule is not None else without_b
        return "OBEY" if obeys else "VIOLATE"


class SequenceRunner:
    """Mock model whose obedience follows a per-arm sequence (to exercise trial averaging)."""

    def __init__(self, with_seq, without_seq):
        self.with_seq, self.without_seq = list(with_seq), list(without_seq)
        self.i_with = self.i_without = 0

    def run(self, task, rule):
        if rule is not None:
            v = self.with_seq[self.i_with % len(self.with_seq)]
            self.i_with += 1
        else:
            v = self.without_seq[self.i_without % len(self.without_seq)]
            self.i_without += 1
        return "OBEY" if v else "VIOLATE"


class MarkerJudge:
    def obeys(self, rule, task, output, criterion):
        return output == "OBEY"


def _rule(rid, tasks):
    return RuleCard(
        rid,
        f"rule text for {rid}",
        tuple(Scenario(f"s{i}", t, "applies") for i, t in enumerate(tasks)),
    )


def test_keep_when_rule_moves_behaviour():
    tasks = ["a", "b", "c", "d"]
    runner = TableRunner({t: (True, False) for t in tasks})
    r = measure(_rule("keep-rule", tasks), runner, MarkerJudge())
    assert r.adherence_with == 1.0 and r.adherence_without == 0.0
    assert r.lift == 1.0
    assert r.verdict == "keep"


def test_dead_weight_when_model_already_complies():
    tasks = ["a", "b", "c", "d"]
    runner = TableRunner({t: (True, True) for t in tasks})
    r = measure(_rule("bloat-rule", tasks), runner, MarkerJudge())
    assert r.adherence_with == 1.0 and r.adherence_without == 1.0
    assert r.lift == 0.0
    assert r.verdict == "dead-weight"


def test_ineffective_when_ignored_even_when_present():
    tasks = ["a", "b", "c", "d", "e"]
    table = {t: (i == 0, False) for i, t in enumerate(tasks)}
    runner = TableRunner(table)
    r = measure(_rule("ignored-rule", tasks), runner, MarkerJudge())
    assert r.adherence_with == pytest.approx(0.2)
    assert r.verdict == "ineffective"
    assert "gate" in r.action


def test_weak_when_small_lift_over_a_middling_floor():
    tasks = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
    table = {}
    for i, t in enumerate(tasks):
        table[t] = (i < 6, i < 5)
    r = measure(_rule("weak-rule", tasks), TableRunner(table), MarkerJudge())
    assert r.adherence_with == pytest.approx(0.6)
    assert r.adherence_without == pytest.approx(0.5)
    assert r.lift == pytest.approx(0.1)
    assert r.verdict == "weak"


def test_per_scenario_lift_recorded():
    tasks = ["x", "y"]
    runner = TableRunner({"x": (True, False), "y": (False, False)})
    r = measure(_rule("mixed", tasks), runner, MarkerJudge())
    by_id = {s.scenario_id: s for s in r.per_scenario}
    assert by_id["s0"].lift == 1.0
    assert by_id["s1"].lift == 0.0
    assert r.lift == pytest.approx(0.5)


def test_trials_average_out_nondeterminism():
    runner = SequenceRunner(with_seq=[True, False], without_seq=[False, False])
    r = measure(_rule("noisy", ["only"]), runner, MarkerJudge(), trials=2)
    assert r.adherence_with == pytest.approx(0.5)
    assert r.adherence_without == 0.0
    assert r.trials == 2


def test_rejects_bad_input():
    with pytest.raises(ValueError):
        measure(_rule("r", ["a"]), TableRunner({"a": (True, True)}), MarkerJudge(), trials=0)
    with pytest.raises(ValueError):
        measure(RuleCard("empty", "t", ()), TableRunner({}), MarkerJudge())


def test_format_report_is_readable():
    tasks = ["a", "b"]
    runner = TableRunner({t: (True, False) for t in tasks})
    out = format_report(measure(_rule("fmt", tasks), runner, MarkerJudge()))
    assert "keep" in out and "lift" in out and "100%" in out
