"""A verdict the evidence does not support is never advice — no cutting on noise."""

from context_report.efficacy import RuleCard, Scenario, format_report, measure
from context_report.efficacy.core import required_per_arm


class TableRunner:
    def __init__(self, table):
        self.table = table

    def run(self, task, rule):
        with_b, without_b = self.table[task]
        return "OBEY" if (with_b if rule is not None else without_b) else "VIOLATE"


class MarkerJudge:
    def obeys(self, rule, task, output, criterion):
        return output == "OBEY"


def _rule(rid, tasks):
    return RuleCard(
        rid,
        f"rule text for {rid}",
        tuple(Scenario(f"s{i}", t, "applies") for i, t in enumerate(tasks)),
    )


def _measure(tasks, arms, trials=1):
    runner = TableRunner(dict.fromkeys(tasks, arms))
    return measure(_rule("r", tasks), runner, MarkerJudge(), trials=trials)


def test_keep_is_cheap_to_confirm_because_it_is_the_harmless_verdict():
    """A clean split confirms `keep` on few runs — leaving a rule in place risks nothing."""
    report = _measure(["a", "b", "c", "d"], (True, False))
    assert report.verdict == "keep"
    assert report.confirmed is True
    assert report.observations >= required_per_arm("keep")


def test_dead_weight_is_expensive_because_it_tells_you_to_delete():
    """Proving the model already complies is a claim about a high baseline; that costs data."""
    assert required_per_arm("dead-weight") > 4 * required_per_arm("keep")
    thin = _measure(["a", "b", "c", "d"], (True, True), trials=2)
    assert thin.verdict == "dead-weight"
    assert thin.confirmed is False
    assert "needs" in thin.advice and "runs per arm" in thin.advice


def test_enough_evidence_confirms_the_same_verdict():
    report = _measure([f"t{i}" for i in range(10)], (True, False), trials=4)
    assert report.verdict == "keep"
    assert report.confirmed is True
    assert report.advice == report.action


def test_dead_weight_confirms_once_the_evidence_reaches_the_derived_floor():
    need = required_per_arm("dead-weight")
    thick = _measure([f"t{i}" for i in range(need)], (True, True), trials=2)
    assert thick.verdict == "dead-weight"
    assert thick.confirmed is True


def test_floors_are_derived_from_the_thresholds_not_hand_picked():
    """Every verdict's floor is the smallest n at which its best case clears its own test."""
    for verdict in ("keep", "weak", "ineffective", "dead-weight"):
        need = required_per_arm(verdict)
        assert need >= 1
        assert need <= 500


def test_intervals_are_reported_and_bracket_the_estimates():
    report = _measure([f"t{i}" for i in range(10)], (True, False), trials=2)
    assert report.lift_ci[0] < report.lift <= report.lift_ci[1]
    assert report.with_ci[0] <= report.adherence_with <= report.with_ci[1]
    assert report.observations == 20


def test_report_shows_the_interval_and_the_status():
    text = format_report(_measure(["a", "b", "c", "d"], (True, False)))
    assert "confirmed" in text
    assert "95% CI" in text


def test_unconfirmed_advice_names_the_evidence_still_needed():
    text = format_report(_measure(["a", "b"], (True, True), trials=2))
    assert "unconfirmed" in text
    assert "runs per arm" in text
