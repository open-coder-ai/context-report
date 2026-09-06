"""The `efficacy` subcommand: a dry run costs nothing, and a real run reports one row per rule."""

import json

from context_report.cli import main
from context_report.efficacy import cli as efficacy_cli

INSTRUCTIONS = """# Rules

- Never use field injection
- Always write a test with the change
"""


class ScriptedAsker:
    """Returns scenario JSON for a scenario prompt, OBEY/YES otherwise."""

    def __init__(self):
        self.calls = 0

    def ask(self, prompt):
        self.calls += 1
        if "JSON array" in prompt:
            return '["write a service class"]'
        if "compliance judge" in prompt:
            return "YES" if "Follow this rule" in prompt else "NO"
        return f"code for: {prompt[:20]}"


def _project(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(INSTRUCTIONS, encoding="utf-8")
    return tmp_path


def test_dry_run_lists_rules_and_budget_without_calling_a_model(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(_project(tmp_path))

    def _boom(_args):
        raise AssertionError("a dry run must not reach a backend")

    monkeypatch.setattr(efficacy_cli, "_askers", _boom)
    assert main(["efficacy", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "2 candidate rule(s)" in out
    assert "Never use field injection" in out
    assert "model call(s)" in out


def test_no_instruction_files_is_an_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["efficacy", "--dry-run"]) == 1
    assert "no instruction files" in capsys.readouterr().err


def test_only_filters_to_named_rules(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(_project(tmp_path))
    main(["efficacy", "--dry-run", "--only", "CLAUDE.md:3"])
    out = capsys.readouterr().out
    assert "1 candidate rule(s)" in out
    assert "Never use field injection" in out


def test_json_run_reports_a_row_per_rule(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(_project(tmp_path))
    asker = ScriptedAsker()
    monkeypatch.setattr(efficacy_cli, "_askers", lambda args: (asker, asker))
    assert main(["efficacy", "--json", "--scenarios-per-rule", "1"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 2
    assert {"rule_id", "verdict", "confirmed", "advice", "lift_ci"} <= set(rows[0])
    assert rows[0]["confirmed"] is False, "one scenario, one trial can never confirm"


def test_hand_written_scenarios_skip_generation(tmp_path, capsys, monkeypatch):
    project = _project(tmp_path)
    (project / "scen.json").write_text(
        json.dumps({"CLAUDE.md:3": ["task a"], "CLAUDE.md:4": ["task b"]}), encoding="utf-8"
    )
    monkeypatch.chdir(project)
    asker = ScriptedAsker()
    monkeypatch.setattr(efficacy_cli, "_askers", lambda args: (asker, asker))
    assert main(["efficacy", "--json", "--scenarios", "scen.json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["scenarios"] == 1
