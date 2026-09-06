"""Grade recorded arms: by code where a rule's criterion allows it, by a judge model when given."""

from __future__ import annotations

from dataclasses import dataclass, field

from context_report.efficacy.core import AdherenceReport, Judge, RuleCard, Runner, measure
from context_report.efficacy.fastjudge import (
    DEFAULT_CHECKERS,
    CannotJudgeError,
    Checker,
    FastPathJudge,
)

JUDGE_DETERMINISTIC = "deterministic"
JUDGE_MODEL = "model"


class DeterministicOnlyJudge:
    """The fallback when no judge model is configured: prose criteria cannot be graded."""

    def obeys(self, rule: str, task: str, output: str, criterion: str) -> bool:  # noqa: ARG002
        raise CannotJudgeError(f"no judge model configured; rule needs one: {rule[:60]!r}")


@dataclass(frozen=True)
class Graded:
    """What grading produced: reports for gradable rules, and the ids of the rules it could not."""

    reports: tuple[AdherenceReport, ...] = field(default_factory=tuple)
    ungraded: tuple[str, ...] = field(default_factory=tuple)
    judge: str = JUDGE_DETERMINISTIC


def grade(
    cards: list[RuleCard],
    runner: Runner,
    judge: Judge | None,
    trials: int,
    checkers: tuple[Checker, ...] = (),
) -> Graded:
    """Measure every card; a rule the judge cannot grade is reported ungraded, never guessed.

    `checkers` are case-specific deterministic graders (eval-case regex graders); they run before
    the built-in code checkers, and before any judge model.
    """
    fallback: Judge = judge if judge is not None else DeterministicOnlyJudge()
    fast = FastPathJudge(fallback, checkers=(*checkers, *DEFAULT_CHECKERS))
    reports: list[AdherenceReport] = []
    ungraded: list[str] = []
    for card in cards:
        try:
            reports.append(measure(card, runner, fast, trials))
        except CannotJudgeError:
            ungraded.append(card.id)
    return Graded(
        reports=tuple(reports),
        ungraded=tuple(ungraded),
        judge=JUDGE_MODEL if judge is not None else JUDGE_DETERMINISTIC,
    )
