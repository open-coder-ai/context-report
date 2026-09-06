"""The `claude plugin eval` case layout compiles to the same task shape a JSON tasks file uses."""

from __future__ import annotations

from pathlib import Path

import pytest

from context_report.efficacy.fastjudge import GraderRegex
from context_report.run import evalcases
from context_report.run.manifest import ManifestError, Subject, Task


def _subject(tmp_path: Path, name: str) -> Subject:
    path = tmp_path / name
    path.mkdir()
    return Subject(id=name, path=path.resolve(), kind="plugin")


def _case(tmp_path: Path, name: str, prompt_frontmatter: str, body: str = "Do the thing.") -> Path:
    case_dir = tmp_path / "evals" / name
    case_dir.mkdir(parents=True)
    (case_dir / "prompt.md").write_text(f"---\n{prompt_frontmatter}---\n{body}\n")
    return case_dir


def _grader(case_dir: Path, name: str, frontmatter: str, body: str = "") -> None:
    graders = case_dir / "graders"
    graders.mkdir(exist_ok=True)
    (graders / f"{name}.md").write_text(f"---\n{frontmatter}---\n{body}")


def test_case_with_no_plugins_defaults_to_every_subject(tmp_path: Path) -> None:
    subjects = (_subject(tmp_path, "a"), _subject(tmp_path, "b"))
    _case(tmp_path, "c1", "name: c1\n")
    tasks = evalcases.load_dir(tmp_path / "evals", subjects)
    assert tasks[0]["subjects"] == ()  # empty means "every subject", same as a JSON task


def test_plugins_path_resolves_to_the_matching_subject(tmp_path: Path) -> None:
    subjects = (_subject(tmp_path, "a"), _subject(tmp_path, "b"))
    _case(tmp_path, "c1", "plugins:\n  - ../../a\n")
    tasks = evalcases.load_dir(tmp_path / "evals", subjects)
    assert tasks[0]["subjects"] == ("a",)


def test_plugins_path_matching_no_subject_names_both_in_the_error(tmp_path: Path) -> None:
    subjects = (_subject(tmp_path, "a"),)
    _case(tmp_path, "c1", "plugins:\n  - ../../ghost\n")
    with pytest.raises(ManifestError, match="ghost") as exc:
        evalcases.load_dir(tmp_path / "evals", subjects)
    assert "no subject" in str(exc.value)


def test_rule_tags_become_rules_other_tags_are_kept(tmp_path: Path) -> None:
    _case(tmp_path, "c1", "tags:\n  - rule:never-do-x\n  - smoke\n")
    tasks = evalcases.load_dir(tmp_path / "evals", ())
    assert tasks[0]["rules"] == ("never-do-x",)
    assert tasks[0]["tags"] == ("smoke",)


def test_prompt_body_is_the_frontmatter_stripped_trimmed_text(tmp_path: Path) -> None:
    _case(tmp_path, "c1", "name: c1\n", body="  Ship it.  \n\nReally.")
    tasks = evalcases.load_dir(tmp_path / "evals", ())
    assert tasks[0]["prompt"] == "Ship it.  \n\nReally."


def test_missing_frontmatter_block_is_rejected(tmp_path: Path) -> None:
    case_dir = tmp_path / "evals" / "c1"
    case_dir.mkdir(parents=True)
    (case_dir / "prompt.md").write_text("Just a prompt, no frontmatter.\n")
    with pytest.raises(ManifestError, match="frontmatter"):
        evalcases.load_dir(tmp_path / "evals", ())


def test_malformed_frontmatter_yaml_is_rejected(tmp_path: Path) -> None:
    case_dir = tmp_path / "evals" / "c1"
    case_dir.mkdir(parents=True)
    (case_dir / "prompt.md").write_text("---\ntags: [unterminated\n---\nDo it.\n")
    with pytest.raises(ManifestError, match="malformed"):
        evalcases.load_dir(tmp_path / "evals", ())


def test_llm_grader_with_no_rule_tag_binds_to_the_star_key(tmp_path: Path) -> None:
    case_dir = _case(tmp_path, "c1", "name: c1\n")
    _grader(case_dir, "g1", "type: llm\ncriteria: Be nice.\n")
    tasks = evalcases.load_dir(tmp_path / "evals", ())
    assert tasks[0]["criteria"] == {"*": "Be nice."}


def test_llm_grader_binds_to_the_cases_named_rule(tmp_path: Path) -> None:
    case_dir = _case(tmp_path, "c1", "tags:\n  - rule:r1\n")
    _grader(case_dir, "g1", "type: llm\ncriteria: Be nice.\n")
    tasks = evalcases.load_dir(tmp_path / "evals", ())
    assert tasks[0]["criteria"] == {"r1": "Be nice."}


def test_llm_grader_with_its_own_rule_field_overrides_the_case_tags(tmp_path: Path) -> None:
    case_dir = _case(tmp_path, "c1", "tags:\n  - rule:r1\n")
    _grader(case_dir, "g1", "type: llm\nrule: r2\ncriteria: Be nice.\n")
    tasks = evalcases.load_dir(tmp_path / "evals", ())
    assert tasks[0]["criteria"] == {"r2": "Be nice."}


def test_two_llm_graders_on_the_same_rule_are_joined(tmp_path: Path) -> None:
    case_dir = _case(tmp_path, "c1", "tags:\n  - rule:r1\n")
    _grader(case_dir, "g1", "type: llm\ncriteria: First.\n")
    _grader(case_dir, "g2", "type: llm\ncriteria: Second.\n")
    tasks = evalcases.load_dir(tmp_path / "evals", ())
    assert tasks[0]["criteria"]["r1"] == "First.\n\nSecond."


def test_llm_grader_missing_criteria_is_rejected(tmp_path: Path) -> None:
    case_dir = _case(tmp_path, "c1", "name: c1\n")
    _grader(case_dir, "g1", "type: llm\n")
    with pytest.raises(ManifestError, match="criteria"):
        evalcases.load_dir(tmp_path / "evals", ())


def test_regex_grader_on_last_message_becomes_a_regex_spec(tmp_path: Path) -> None:
    case_dir = _case(tmp_path, "c1", "tags:\n  - rule:r1\n")
    _grader(case_dir, "g1", "type: regex\npattern: foo\nmatch: contains\n")
    tasks = evalcases.load_dir(tmp_path / "evals", ())
    expected = {"pattern": "foo", "flags": "", "match": "contains", "rule_ids": ("r1",)}
    assert tasks[0]["regex_graders"] == (expected,)
    assert tasks[0]["vendor_graders"] == ()


def test_regex_grader_on_a_non_last_message_target_is_vendor_only(tmp_path: Path) -> None:
    case_dir = _case(tmp_path, "c1", "name: c1\n")
    _grader(case_dir, "g1", "type: regex\npattern: foo\ntarget: trace\n")
    tasks = evalcases.load_dir(tmp_path / "evals", ())
    assert tasks[0]["regex_graders"] == ()
    assert tasks[0]["vendor_graders"][0]["target"] == "trace"


@pytest.mark.parametrize("grader_type", ["tool_used", "tool_order", "file_exists", "baseline"])
def test_unrunnable_grader_types_are_recorded_as_vendor_graders(
    tmp_path: Path, grader_type: str
) -> None:
    case_dir = _case(tmp_path, "c1", "name: c1\n")
    _grader(case_dir, "g1", f"type: {grader_type}\n")
    tasks = evalcases.load_dir(tmp_path / "evals", ())
    assert tasks[0]["vendor_graders"][0]["type"] == grader_type
    assert tasks[0]["criteria"] == {}


def test_unknown_grader_type_is_rejected(tmp_path: Path) -> None:
    case_dir = _case(tmp_path, "c1", "name: c1\n")
    _grader(case_dir, "g1", "type: mystery\n")
    with pytest.raises(ManifestError, match="mystery"):
        evalcases.load_dir(tmp_path / "evals", ())


def test_grader_missing_type_is_rejected(tmp_path: Path) -> None:
    case_dir = _case(tmp_path, "c1", "name: c1\n")
    _grader(case_dir, "g1", "pattern: foo\n")
    with pytest.raises(ManifestError, match="type"):
        evalcases.load_dir(tmp_path / "evals", ())


def test_runs_field_is_carried_through(tmp_path: Path) -> None:
    _case(tmp_path, "c1", "runs: 5\n")
    tasks = evalcases.load_dir(tmp_path / "evals", ())
    assert tasks[0]["runs"] == 5


def test_runs_defaults_to_none(tmp_path: Path) -> None:
    _case(tmp_path, "c1", "name: c1\n")
    tasks = evalcases.load_dir(tmp_path / "evals", ())
    assert tasks[0]["runs"] is None


def test_case_yaml_is_ignored(tmp_path: Path) -> None:
    case_dir = _case(tmp_path, "c1", "name: c1\n")
    (case_dir / "case.yaml").write_text("setup: {}\n")
    tasks = evalcases.load_dir(tmp_path / "evals", ())
    assert len(tasks) == 1


def test_top_level_mocks_directory_is_ignored(tmp_path: Path) -> None:
    _case(tmp_path, "c1", "name: c1\n")
    mocks = tmp_path / "evals" / "mocks" / "server"
    mocks.mkdir(parents=True)
    (mocks / "tool.md").write_text("mock response\n")
    tasks = evalcases.load_dir(tmp_path / "evals", ())
    assert [t["id"] for t in tasks] == ["c1"]


def test_case_directory_without_prompt_md_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "evals" / "empty").mkdir(parents=True)
    with pytest.raises(ManifestError, match=r"prompt\.md"):
        evalcases.load_dir(tmp_path / "evals", ())


def test_tasks_directory_not_found_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="not found"):
        evalcases.load_dir(tmp_path / "no-such-dir", ())


def test_cases_are_loaded_in_sorted_order(tmp_path: Path) -> None:
    _case(tmp_path, "zeta", "name: zeta\n")
    _case(tmp_path, "alpha", "name: alpha\n")
    tasks = evalcases.load_dir(tmp_path / "evals", ())
    assert [t["id"] for t in tasks] == ["alpha", "zeta"]


def test_checkers_for_builds_one_graderregex_per_regex_spec() -> None:
    task = Task(
        id="c1",
        prompt="x",
        subjects=(),
        rules=("r1",),
        regex_graders=(
            {"pattern": "no", "flags": "", "match": "not_contains", "rule_ids": ("r1",)},
        ),
    )
    checkers = evalcases.checkers_for((task,))
    assert len(checkers) == 1
    checker = checkers[0]
    assert isinstance(checker, GraderRegex)
    assert checker.applies("r1") and not checker.applies("r2")
    assert checker.obeys("r1", "all clear") is True
    assert checker.obeys("r1", "no thanks") is False


def test_checkers_for_is_empty_when_no_task_has_regex_graders() -> None:
    task = Task(id="c1", prompt="x", subjects=(), rules=())
    assert evalcases.checkers_for((task,)) == ()
