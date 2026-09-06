"""The `efficacy` row: a claimed estimate of lift, with everything a reader needs to discount it."""

from __future__ import annotations

from typing import Any

from context_report.efficacy.core import AdherenceReport
from context_report.efficacy.grade import Graded
from context_report.efficacy.stats import newcombe_diff
from context_report.rows import CLAIMED, FAILED, NOT_AVAILABLE, PASSED, WARNED, Estimate, Row

ATTRIBUTE = "efficacy"
CONFIDENCE = 0.95
VALUES_UNEXERCISED = "unexercised"  # rule ids no task exercised: a fact about the subject
# v0.1's ablation: the rule text is prepended to the task prompt. It is not a client install,
# and the row says so, so nobody reads a prompt-prefix result as an installed-plugin result.
ABLATION_PROMPT_PREFIX = "prompt-prefix-v1"


def pooled_lift(reports: tuple[AdherenceReport, ...]) -> tuple[float, tuple[float, float]]:
    """Lift over all observations of all graded rules, with a Newcombe interval."""
    n = sum(r.observations for r in reports)
    with_hits = sum(r.adherence_with * r.observations for r in reports)
    without_hits = sum(r.adherence_without * r.observations for r in reports)
    lift = (with_hits - without_hits) / n
    return lift, newcombe_diff(with_hits, n, without_hits, n)


def _result(lift: float, ci: tuple[float, float]) -> str:
    lower, upper = ci
    if lower <= 0:
        return FAILED  # no distinguishable effect in the declared direction
    return WARNED if (upper - lower) > lift else PASSED  # interval wide relative to the point


def _per_rule(r: AdherenceReport) -> dict[str, Any]:
    return {
        "ruleId": r.rule_id,
        "lift": r.lift,
        "liftCI": list(r.lift_ci),
        "adherenceWith": r.adherence_with,
        "adherenceWithout": r.adherence_without,
        "observationsPerArm": r.observations,
        "verdict": r.verdict,
        "confirmed": r.confirmed,
    }


def efficacy_row(  # noqa: PLR0913 -- keyword-only; these are the conditions the row must carry
    graded: Graded,
    *,
    model: str,
    judge_model: str | None,
    measured_on: str,
    n_per_arm: int,
    ablation: str = ABLATION_PROMPT_PREFIX,
    tokens_per_arm: dict[str, Any] | None = None,
    transcripts: int = 0,
    unexercised: list[str] | tuple[str, ...] = (),
) -> Row:
    """Always `claimed`; with nothing graded it is NotAvailable and says what was recorded."""
    conditions: dict[str, Any] = {
        "ablation": ablation,
        "model": model,
        "judgeModel": judge_model,
        "judge": graded.judge,
        "measuredOn": measured_on,
        "nPerArm": n_per_arm,
    }
    values: dict[str, Any] = {
        "perRule": [_per_rule(r) for r in graded.reports],
        "ungraded": list(graded.ungraded),
    }
    if tokens_per_arm is not None:
        values["tokensPerArm"] = dict(tokens_per_arm)
    if unexercised:
        values[VALUES_UNEXERCISED] = list(unexercised)
    if not graded.reports:
        why = (
            f"no rule could be graded: {len(graded.ungraded)} rule(s) have a prose criterion and "
            f"no judge model was configured; {transcripts} paired transcripts recorded under "
            "byproducts"
        )
        return Row(
            attribute=ATTRIBUTE,
            basis=CLAIMED,
            result=NOT_AVAILABLE,
            conditions=conditions,
            values=values,
            reasoning=why,
        )
    lift, ci = pooled_lift(graded.reports)
    reasoning = None
    if graded.ungraded:
        reasoning = (
            f"{len(graded.ungraded)} rule(s) ungraded (prose criterion, no judge model): "
            + ", ".join(graded.ungraded)
        )
    return Row(
        attribute=ATTRIBUTE,
        basis=CLAIMED,
        result=_result(lift, ci),
        conditions=conditions,
        values=values,
        estimate=Estimate(
            point_estimate=lift, confidence_level=CONFIDENCE, lower_bound=ci[0], upper_bound=ci[1]
        ),
        reasoning=reasoning,
    )
