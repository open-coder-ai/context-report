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
    rules = extract_all(injected_text_paths(subject.path, subject.kind)).rules
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
                id=task.id, task=task.prompt, rule_applies=task.criteria.get(rule.id, rule.text)
            )
            for task in manifest.tasks_for(subject.id)
            if not task.rules or rule.id in task.rules
        )
        if scenarios:
            cards.append(RuleCard(id=rule.id, text=rule.text, scenarios=scenarios))
    return cards


def _all_rule_ids(manifest: Manifest) -> set[str]:
    """Every rule id across every subject: a shared task may name rules from any of them."""
    ids: set[str] = set()
    for s in manifest.subjects:
        ids |= {r.id for r in extract_all(injected_text_paths(s.path, s.kind)).rules}
    return ids


def unexercised_rules(manifest: Manifest, subject: Subject) -> list[str]:
    """Rule ids of the subject that no task exercises: reported, never silently passed."""
    covered = {c.id for c in cards_for(manifest, subject)}
    rules = extract_all(injected_text_paths(subject.path, subject.kind)).rules
    return [r.id for r in rules if r.id not in covered]
