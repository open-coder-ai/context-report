"""Rule cards for one subject: its own rules, exercised by the manifest's tasks that name it."""

from __future__ import annotations

from context_report.efficacy.core import RuleCard, Scenario
from context_report.efficacy.rules import extract_all
from context_report.produce.cost import injected_text_paths
from context_report.run.manifest import Manifest, ManifestError, Subject


def cards_for(manifest: Manifest, subject: Subject) -> list[RuleCard]:
    """One card per rule the subject injects; scenarios are the tasks that exercise that rule.

    A task with no `rules` exercises every rule of the subjects it names. A task's `criteria`
    entry for a rule is that scenario's compliance criterion; otherwise the rule text is.
    Rules no task exercises get no card, so they surface as unmeasured, never as passing.
    """
    rules = _rules_of(subject, manifest)
    known = {r.id for r in rules}
    for task in manifest.tasks_for(subject.id):
        unknown = sorted(set(task.rules) - known)
        if unknown and (len(task.subjects) == 1 or set(task.rules) - _all_rule_ids(manifest)):
            raise ManifestError(
                f"task {task.id!r} names rule(s) {unknown} that subject {subject.id!r} does not "
                f"have; its rule ids are {sorted(known)}"
            )
    cards: list[RuleCard] = []
    for rule in rules:
        scenarios = tuple(
            Scenario(
                id=task.id,
                task=task.prompt,
                # An eval case with no rule: tags binds its llm grader to every rule as "*".
                rule_applies=task.criteria.get(rule.id) or task.criteria.get("*") or rule.text,
            )
            for task in manifest.tasks_for(subject.id)
            if not task.rules or rule.id in task.rules
        )
        if scenarios:
            cards.append(RuleCard(id=rule.id, text=rule.text, scenarios=scenarios))
    return cards


def _rules_of(subject: Subject, manifest: Manifest) -> list:
    """The subject's extracted rules, plus any passed-over block a task names by id.

    The extractor is a heuristic; a case author who tags `rule:<id>` for a block it read as
    description knows better, and that block becomes a rule for this run, in source order.
    """
    found = extract_all(injected_text_paths(subject.path, subject.kind))
    named = {rid for task in manifest.tasks_for(subject.id) for rid in task.rules}
    known = {r.id for r in found.rules}
    promoted = [c for c in found.candidates if c.id in named and c.id not in known]
    return sorted([*found.rules, *promoted], key=lambda r: (r.source, r.line))


def _all_rule_ids(manifest: Manifest) -> set[str]:
    """Every rule id across every subject: a shared task may name rules from any of them."""
    ids: set[str] = set()
    for s in manifest.subjects:
        ids |= {r.id for r in _rules_of(s, manifest)}
    return ids


def unexercised_rules(manifest: Manifest, subject: Subject) -> list[str]:
    """Rule ids of the subject that no task exercises: reported, never silently passed."""
    covered = {c.id for c in cards_for(manifest, subject)}
    return [r.id for r in _rules_of(subject, manifest) if r.id not in covered]


def check_all(manifest: Manifest) -> None:
    """Build every subject's cards up front, so one bad tag is reported for all subjects at once
    rather than aborting a run after earlier subjects have already spent their calls."""
    problems = []
    for subject in manifest.subjects:
        try:
            cards_for(manifest, subject)
        except ManifestError as exc:
            problems.append(str(exc))
    if problems:
        raise ManifestError("\n".join(problems))
