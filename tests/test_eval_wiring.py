"""An eval case's regex grader grades the arms by code, with no judge model, end to end."""

from __future__ import annotations

import json
from pathlib import Path

from context_report.efficacy import rules
from context_report.rows import CLAIMED, PASSED
from context_report.run import manifest as m
from context_report.run.cards import cards_for
from context_report.run.runner import run

RULE = "No print statements in shipped code."
WITH_MARKER = "Follow this rule strictly:"


class ArmAsker:
    """Obeys the rule only when it is in the prompt; the regex grader must see the difference."""

    def __init__(self) -> None:
        self.calls = 0

    def ask(self, prompt: str) -> str:
        self.calls += 1
        if prompt.startswith(WITH_MARKER):
            return "def f():\n    logging.info('done')\n"
        return "def f():\n    print('debug')\n"


def _project(tmp_path: Path) -> m.Manifest:
    (tmp_path / "AGENTS.md").write_text(f"- {RULE}\n")
    rule_id = rules.slug(RULE)
    case = tmp_path / "evals" / "debug-helper"
    (case / "graders").mkdir(parents=True)
    (case / "prompt.md").write_text(
        f"---\nname: debug helper\ntags: [rule:{rule_id}]\n---\nWrite a debug helper function.\n"
    )
    (case / "graders" / "no-print.md").write_text(
        "---\ntype: regex\npattern: 'print\\('\nmatch: not_contains\n---\n"
    )
    doc = {
        "contextReportRun": "v0.1",
        "subjects": [{"id": "rules", "path": "./AGENTS.md", "kind": "instruction-file"}],
        "target": {"name": "cursor"},
        "models": [{"provider": "anthropic", "id": "m"}],
        "tasks": "evals",
        "arms": {"nPerArm": 3},
        "judge": None,
        "out": "out",
    }
    (tmp_path / "run.json").write_text(json.dumps(doc))
    return m.load(tmp_path / "run.json")


def test_regex_grader_grades_deterministically_without_a_judge(tmp_path: Path) -> None:
    manifest = _project(tmp_path)
    cards = cards_for(manifest, manifest.subject("rules"))
    assert [c.id for c in cards] == [rules.slug(RULE)]
    assert cards[0].scenarios[0].rule_applies == RULE, "no llm grader, so the rule text stands"

    askers: list[ArmAsker] = []

    def factory(model, *, effort=None):  # noqa: ARG001 -- Asker factory contract
        asker = ArmAsker()
        askers.append(asker)
        return asker

    out = run(manifest, asker_factory=factory)
    stmt = json.loads((out / "rules" / "anthropic--m.json").read_text())
    efficacy = next(a for a in stmt["predicate"]["attributes"] if a["attribute"] == "efficacy")
    assert efficacy["basis"] == CLAIMED and efficacy["result"] == PASSED
    assert efficacy["conditions"]["judge"] == "deterministic"
    assert efficacy["conditions"]["judgeModel"] is None
    assert efficacy["values"]["ungraded"] == []
    per_rule = efficacy["values"]["perRule"][0]
    assert per_rule["adherenceWith"] == 1.0 and per_rule["adherenceWithout"] == 0.0
    assert sum(a.calls for a in askers) == 6, "3 trials x 2 arms, and the grader cost no call"


def test_star_criterion_binds_an_untagged_llm_grader_to_every_rule(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text(f"- {RULE}\n- Never commit secrets to the repository.\n")
    case = tmp_path / "evals" / "tidy"
    (case / "graders").mkdir(parents=True)
    (case / "prompt.md").write_text("---\nname: tidy\n---\nTidy the module.\n")
    (case / "graders" / "judge.md").write_text(
        "---\ntype: llm\ncriteria: The change is safe to ship.\n---\n"
    )
    doc = {
        "contextReportRun": "v0.1",
        "subjects": [{"id": "rules", "path": "./AGENTS.md", "kind": "instruction-file"}],
        "target": {"name": "cursor"},
        "models": [],
        "tasks": "evals",
        "arms": {"nPerArm": 1},
        "out": "out",
    }
    (tmp_path / "run.json").write_text(json.dumps(doc))
    manifest = m.load(tmp_path / "run.json")
    cards = cards_for(manifest, manifest.subject("rules"))
    assert len(cards) == 2
    assert all(c.scenarios[0].rule_applies == "The change is safe to ship." for c in cards)
