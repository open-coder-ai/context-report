"""Measure many rules at once, sharing the control arm across them."""

from __future__ import annotations

from dataclasses import dataclass, field

from context_report.efficacy.cache import CachingJudge, CachingRunner, MemStore, Store
from context_report.efficacy.core import AdherenceReport, Judge, RuleCard, Runner, measure


@dataclass(frozen=True)
class CacheSpec:
    """Where shared generations are stored, and the namespace they are keyed under."""

    store: Store | None = None
    model: str = "default"


@dataclass(frozen=True)
class SuiteResult:
    reports: tuple[AdherenceReport, ...] = field(default_factory=tuple)
    runner_calls: int = 0
    runner_hits: int = 0
    judge_calls: int = 0

    @property
    def naive_runner_calls(self) -> int:
        """What it would have cost with no sharing: every scenario, both arms, every trial."""
        return self.runner_calls + self.runner_hits


def measure_suite(
    rules: list[RuleCard],
    runner: Runner,
    judge: Judge,
    trials: int = 1,
    cache: CacheSpec | None = None,
) -> SuiteResult:
    """Measure every rule, sharing generations (notably the control arm) through one cache."""
    cache = cache or CacheSpec()
    store = cache.store or MemStore()
    cr = CachingRunner(runner, store, model=cache.model)
    cj = CachingJudge(judge, store, model=cache.model)
    reports = tuple(measure(rule, cr, cj, trials) for rule in rules)
    return SuiteResult(
        reports=reports,
        runner_calls=cr.misses,
        runner_hits=cr.hits,
        judge_calls=cj.misses,
    )
