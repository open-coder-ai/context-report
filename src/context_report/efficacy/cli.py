"""`context-report efficacy` — measure which rules in your instruction files earn their place."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from context_report.efficacy import scenarios as scenarios_mod
from context_report.efficacy.backends import AskerJudge, AskerRunner
from context_report.efficacy.cache import FileStore
from context_report.efficacy.core import (
    MIN_TRIALS_TO_CUT,
    AdherenceReport,
    format_report,
    required_per_arm,
)
from context_report.efficacy.fastjudge import FastPathJudge
from context_report.efficacy.rules import Extraction, Rule, discover, extract_all
from context_report.efficacy.suite import CacheSpec, measure_suite

DEFAULT_CACHE = ".efficacy-cache.json"
ARMS = 2
CALLS_PER_RUN = 2  # one generation, one judgement


def add_efficacy_parser(subparsers: Any) -> None:
    """Register `efficacy` on the main CLI: paired-ablation measurement of a rule's lift."""
    p = subparsers.add_parser(
        "efficacy",
        help="measure whether the rules in your instruction files change agent behaviour",
    )
    p.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="instruction files (default: the ones found in the current directory)",
    )
    p.add_argument("--trials", type=int, default=1, help="runs per scenario per arm")
    p.add_argument("--scenarios-per-rule", type=int, default=scenarios_mod.DEFAULT_COUNT)
    p.add_argument("--scenarios", type=Path, help="JSON file of hand-written scenarios")
    p.add_argument("--backend", choices=("cli", "api"), default="cli")
    p.add_argument("--model", default=None, help="model id (api backend)")
    p.add_argument("--cache", type=Path, default=Path(DEFAULT_CACHE))
    p.add_argument("--only", action="append", default=[], help="measure only these rule ids")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="list the rules and the call budget without calling a model",
    )


def _collect(paths: list[Path]) -> Extraction:
    files = paths or discover()
    if not files:
        print("no instruction files found — pass paths explicitly", file=sys.stderr)
        return Extraction(rules=[], skipped={})
    return extract_all(files)


def _budget(rules: int, scenarios: int, trials: int, *, generating: bool) -> int:
    generation = rules if generating else 0
    return generation + rules * scenarios * trials * ARMS * CALLS_PER_RUN


def _askers(args: argparse.Namespace) -> tuple[object, object]:
    """(runner asker, judge asker) — the judge runs at low effort where the backend supports it."""
    if args.backend == "api":
        from context_report.efficacy.api_backend import DEFAULT_MODEL, JUDGE_EFFORT, ApiAsker

        model = args.model or DEFAULT_MODEL
        return ApiAsker(model=model), ApiAsker(model=model, effort=JUDGE_EFFORT)
    from context_report.efficacy.cli_backend import CliAsker, available

    if not available():
        raise SystemExit("the `claude` CLI is not on PATH — install it or use --backend api")
    return CliAsker(), CliAsker()


def _as_dict(report: AdherenceReport) -> dict:
    return {
        "rule_id": report.rule_id,
        "verdict": report.verdict,
        "confirmed": report.confirmed,
        "advice": report.advice,
        "adherence_with": report.adherence_with,
        "adherence_without": report.adherence_without,
        "lift": report.lift,
        "lift_ci": list(report.lift_ci),
        "scenarios": report.n,
        "trials": report.trials,
        "observations_per_arm": report.observations,
    }


REPORTED_VERDICTS = ("keep", "ineffective", "dead-weight")


def _print_evidence(rules: int, scenarios: int, trials: int, *, generating: bool) -> None:
    """What the chosen settings can and cannot conclude — before any money is spent."""
    have = scenarios * trials
    print(f"\nevidence: {scenarios} scenario(s) x{trials} trial(s) = {have} runs per arm")
    for verdict in REPORTED_VERDICTS:
        need = required_per_arm(verdict)
        mark = "reachable" if have >= need else f"NOT reachable — needs {need}"
        print(f"  {verdict:<12} {mark}")

    need = max(required_per_arm(v) for v in REPORTED_VERDICTS)
    if have >= need:
        return
    enough_trials = max(trials, MIN_TRIALS_TO_CUT)
    per_rule = max(1, -(-need // enough_trials))
    print("\n  `dead-weight` is the verdict that tells you to delete a rule, and it is the")
    print(f"  most expensive: proving the model already complies needs {need} runs per arm,")
    print(f"  and a cut verdict needs >= {MIN_TRIALS_TO_CUT} trials per scenario so run-to-run")
    print("  variation is actually sampled.")
    print(
        f"  To reach every verdict: --scenarios-per-rule {per_rule} --trials {enough_trials} "
        f"({_budget(rules, per_rule, enough_trials, generating=generating):,} calls)."
    )


def _print_rules(rules: list[Rule], skipped: dict[str, int], budget: int) -> None:
    print(f"{len(rules)} candidate rule(s):\n")
    for rule in rules:
        print(f"  {rule.id:<24} {rule.text}")
    if skipped:
        print("\npassed over:")
        for reason, count in sorted(skipped.items()):
            print(f"  {count:>4}  {reason}")
    print(f"\nup to {budget} model call(s) before caching; re-runs reuse the cache.")


def run_efficacy(args: argparse.Namespace) -> int:
    """`context-report efficacy`: a dry run prints the budget; otherwise measure and report."""
    found = _collect(args.paths)
    rules = found.rules
    if args.only:
        rules = [r for r in rules if r.id in set(args.only)]
    if not rules:
        return 1

    supplied = scenarios_mod.load(args.scenarios) if args.scenarios else {}
    budget = _budget(len(rules), args.scenarios_per_rule, args.trials, generating=not supplied)
    if args.dry_run:
        _print_rules(rules, found.skipped, budget)
        _print_evidence(len(rules), args.scenarios_per_rule, args.trials, generating=not supplied)
        return 0

    runner_asker, judge_asker = _askers(args)
    cards = [
        scenarios_mod.card(
            rule,
            supplied.get(rule.id)
            or scenarios_mod.generate(rule, runner_asker, args.scenarios_per_rule),
        )
        for rule in rules
    ]
    result = measure_suite(
        cards,
        AskerRunner(runner_asker),
        FastPathJudge(AskerJudge(judge_asker)),
        trials=args.trials,
        cache=CacheSpec(store=FileStore(args.cache), model=args.model or args.backend),
    )
    if args.json:
        print(json.dumps([_as_dict(r) for r in result.reports], indent=2))
        return 0
    for report in result.reports:
        print(format_report(report))
        print()
    print(f"{result.runner_calls} model call(s), {result.runner_hits} reused from cache.")
    return 0
