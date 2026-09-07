"""Rule-adherence measurement: does the agent obey rule X, and does the rule earn its place?"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from context_report.efficacy.stats import newcombe_diff, wilson

_FLOOR_ALREADY_HIGH = 0.9
_LIFT_NEGLIGIBLE = 0.1
_COMPLIANCE_FLOOR = 0.5
_LIFT_MEANINGFUL = 0.2
MIN_TRIALS_TO_CUT = 2
_CUT_VERDICTS = frozenset({"dead-weight", "ineffective"})
_SEARCH_CEILING = 500


@dataclass(frozen=True)
class Scenario:
    """One coding task where the rule is relevant and could be obeyed or violated."""

    id: str
    task: str
    rule_applies: str


@dataclass(frozen=True)
class RuleCard:
    """A rule under test plus the scenarios that exercise it."""

    id: str
    text: str
    scenarios: tuple[Scenario, ...]


class Runner(Protocol):
    """Produce agent output for a task. ``rule=None`` is the control arm (rule absent)."""

    def run(self, task: str, rule: str | None) -> str:
        """The agent's output for `task`, with `rule` prepended when given."""


class Judge(Protocol):
    """Decide whether an output met this case's criterion. Deterministic where possible; else LLM.

    ``criterion`` is the scenario's own ``rule_applies`` — what compliance looks like *here*.
    It is a required argument so that a judge has to decide what to do with it: an optional one
    is how the criterion came to be carried and never consulted.
    """

    def obeys(self, rule: str, task: str, output: str, criterion: str) -> bool:
        """True when `output` met `criterion` for this task."""


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    obeyed_with: float
    obeyed_without: float

    @property
    def lift(self) -> float:
        return self.obeyed_with - self.obeyed_without


@dataclass(frozen=True)
class Evidence:
    """How much was observed, and how tightly it pins each proportion."""

    observations: int
    trials: int
    with_ci: tuple[float, float]
    without_ci: tuple[float, float]
    lift_ci: tuple[float, float]


@dataclass(frozen=True)
class AdherenceReport:
    rule_id: str
    n: int
    trials: int
    adherence_with: float
    adherence_without: float
    lift: float
    verdict: str
    action: str
    per_scenario: tuple[ScenarioResult, ...] = field(default_factory=tuple)
    observations: int = 0
    with_ci: tuple[float, float] = (0.0, 1.0)
    without_ci: tuple[float, float] = (0.0, 1.0)
    lift_ci: tuple[float, float] = (-1.0, 1.0)
    confirmed: bool = False

    @property
    def advice(self) -> str:
        """What to actually do — a verdict the interval does not support is not advice."""
        if self.confirmed:
            return self.action
        return _UNCONFIRMED.format(
            needed=max(required_per_arm(self.verdict), self.observations + 1),
            have=self.observations,
        )


_UNCONFIRMED = (
    "not enough evidence yet — this verdict needs {needed} runs per arm "
    "and has {have}; add scenarios or trials before acting on it"
)

_ACTIONS = {
    "keep": "load-bearing — keep it",
    "dead-weight": "model already complies without it — cut it to save context/tokens",
    "ineffective": "ignored even when present — reword, or escalate advise -> gate (chock hook)",
    "weak": "helps a little but compliance is shaky — strengthen or watch",
}


def _verdict(adherence_with: float, adherence_without: float, lift: float) -> str:
    if adherence_with < _COMPLIANCE_FLOOR:
        return "ineffective"
    if adherence_without >= _FLOOR_ALREADY_HIGH and lift <= _LIFT_NEGLIGIBLE:
        return "dead-weight"
    if lift >= _LIFT_MEANINGFUL:
        return "keep"
    return "weak"


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


_BEST_CASE = {
    "keep": lambda n: (n, 0),
    "dead-weight": lambda n: (n, n),
    "ineffective": lambda _n: (0, 0),
    "weak": lambda n: (n, 0),
}


def _supports(verdict: str, with_hits: float, without_hits: float, n: int) -> bool:
    """Does the evidence itself — intervals, not point estimates — support this verdict?"""
    with_ci = wilson(with_hits, n)
    without_ci = wilson(without_hits, n)
    lift_ci = newcombe_diff(with_hits, n, without_hits, n)
    if verdict == "keep":
        return lift_ci[0] >= _LIFT_MEANINGFUL
    if verdict == "dead-weight":
        return without_ci[0] >= _FLOOR_ALREADY_HIGH and lift_ci[1] <= _LIFT_NEGLIGIBLE
    if verdict == "ineffective":
        return with_ci[1] < _COMPLIANCE_FLOOR
    return lift_ci[1] - lift_ci[0] <= _LIFT_NEGLIGIBLE


def required_per_arm(verdict: str) -> int:
    """Runs per arm below which this verdict can never be confirmed, however clean the result.

    Derived from the thresholds by searching the most favourable observation for the verdict —
    not a hand-picked floor. `dead-weight` is the expensive one: proving "the model already
    complies" is a claim about a high baseline, and high baselines need data.
    """
    best_case = _BEST_CASE[verdict]
    for n in range(1, _SEARCH_CEILING + 1):
        with_hits, without_hits = best_case(n)
        if _supports(verdict, with_hits, without_hits, n):
            return n
    return _SEARCH_CEILING


def compute_verdict(adherence_with: float, adherence_without: float, lift: float) -> str:
    """Public wrapper over `_verdict`, for adapters that measure arms outside `measure()`."""
    return _verdict(adherence_with, adherence_without, lift)


def action_for(verdict: str) -> str:
    """Public accessor for `_ACTIONS`, so an adapter doesn't need the private table itself."""
    return _ACTIONS[verdict]


def _confirms(verdict: str, evidence: Evidence) -> bool:
    """True when the evidence — not just the point estimate — supports acting on the verdict."""
    if evidence.observations < required_per_arm(verdict):
        return False
    if verdict in _CUT_VERDICTS and evidence.trials < MIN_TRIALS_TO_CUT:
        return False
    if verdict == "keep":
        return evidence.lift_ci[0] >= _LIFT_MEANINGFUL
    if verdict == "dead-weight":
        return (
            evidence.without_ci[0] >= _FLOOR_ALREADY_HIGH
            and evidence.lift_ci[1] <= _LIFT_NEGLIGIBLE
        )
    if verdict == "ineffective":
        return evidence.with_ci[1] < _COMPLIANCE_FLOOR
    return evidence.lift_ci[1] - evidence.lift_ci[0] <= _LIFT_NEGLIGIBLE


def verdict_confirmed(verdict: str, evidence: Evidence) -> bool:
    """Public wrapper over `_confirms`, for adapters that measure arms outside `measure()`."""
    return _confirms(verdict, evidence)


def measure(rule: RuleCard, runner: Runner, judge: Judge, trials: int = 1) -> AdherenceReport:
    """Measure whether ``rule`` changes the agent's behaviour, per scenario and in aggregate."""
    if trials < 1:
        raise ValueError("trials must be >= 1")
    if not rule.scenarios:
        raise ValueError(f"rule {rule.id!r} has no scenarios to measure")

    per_scenario: list[ScenarioResult] = []
    for s in rule.scenarios:
        with_hits = [
            1.0
            if judge.obeys(rule.text, s.task, runner.run(s.task, rule.text), s.rule_applies)
            else 0.0
            for _ in range(trials)
        ]
        without_hits = [
            1.0 if judge.obeys(rule.text, s.task, runner.run(s.task, None), s.rule_applies) else 0.0
            for _ in range(trials)
        ]
        per_scenario.append(ScenarioResult(s.id, _mean(with_hits), _mean(without_hits)))

    adherence_with = _mean([r.obeyed_with for r in per_scenario])
    adherence_without = _mean([r.obeyed_without for r in per_scenario])
    lift = adherence_with - adherence_without
    verdict = _verdict(adherence_with, adherence_without, lift)

    observations = len(per_scenario) * trials
    with_ci = wilson(adherence_with * observations, observations)
    without_ci = wilson(adherence_without * observations, observations)
    evidence = Evidence(
        observations=observations,
        trials=trials,
        with_ci=with_ci,
        without_ci=without_ci,
        lift_ci=newcombe_diff(
            adherence_with * observations,
            observations,
            adherence_without * observations,
            observations,
        ),
    )
    return AdherenceReport(
        rule_id=rule.id,
        n=len(per_scenario),
        trials=trials,
        adherence_with=adherence_with,
        adherence_without=adherence_without,
        lift=lift,
        verdict=verdict,
        action=_ACTIONS[verdict],
        per_scenario=tuple(per_scenario),
        observations=observations,
        with_ci=with_ci,
        without_ci=without_ci,
        lift_ci=evidence.lift_ci,
        confirmed=_confirms(verdict, evidence),
    )


def format_report(report: AdherenceReport) -> str:
    """A one-screen human summary — the thing a developer reads to decide keep/cut/reword."""

    def pct(x: float) -> str:
        return f"{round(x * 100)}%"

    status = "confirmed" if report.confirmed else "unconfirmed"
    lo, hi = report.lift_ci
    lines = [
        f"rule: {report.rule_id}   [{report.verdict}, {status}]",
        f"  obeyed with rule:    {pct(report.adherence_with)}",
        f"  obeyed without rule: {pct(report.adherence_without)}   (what the model already does)",
        f"  lift:                {pct(report.lift)}   95% CI [{pct(lo)}, {pct(hi)}]",
        f"  evidence:            {report.n} scenario(s) x{report.trials}"
        f" = {report.observations} runs per arm",
        f"  -> {report.advice}",
    ]
    return "\n".join(lines)
