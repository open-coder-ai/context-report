"""A manifest is validated and resolved before anything runs; every mistake is named."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from context_report.run import manifest as m

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "spec" / "run" / "v0.1" / "examples"


def _fixtures(tmp_path: Path) -> None:
    """The subjects examples/run.json's worked example names: an instruction file and a plugin."""
    (tmp_path / "AGENTS.md").write_text("- Never commit secrets.\n")
    (tmp_path / "plugins" / "git-safety").mkdir(parents=True)
    (tmp_path / "plugins" / "git-safety" / "SKILL.md").write_text("# git safety\n")


def _write(tmp_path: Path, doc: dict | None = None) -> Path:
    """Build the worked example's subjects and its `evals/` case dir, then write `doc` as run.json.

    `evals/` is copied from the spec's own worked example so its `plugins` entries -- relative
    to each case directory -- resolve against the `plugins/git-safety` this helper also creates.
    """
    _fixtures(tmp_path)
    shutil.copytree(EXAMPLES / "evals", tmp_path / "evals")
    if doc is None:
        doc = _example_doc()
    path = tmp_path / "run.json"
    path.write_text(json.dumps(doc))
    return path


def _example_doc() -> dict:
    return json.loads((EXAMPLES / "run.json").read_text())


def test_package_copy_of_the_schema_is_byte_identical() -> None:
    spec = (ROOT / "spec" / "run" / "v0.1" / "schema.json").read_bytes()
    pkg = (ROOT / "src" / "context_report" / "data" / "run-v0.1.schema.json").read_bytes()
    assert spec == pkg


def test_worked_example_loads_and_resolves(tmp_path: Path) -> None:
    path = _write(tmp_path)
    loaded = m.load(path)
    assert [s.id for s in loaded.subjects] == ["house-rules", "git-safety"]
    assert loaded.subjects[0].path == (tmp_path / "AGENTS.md").resolve()
    assert loaded.target.client_version == "2.1.0"
    assert next(x.slug for x in loaded.models) == "anthropic--claude-sonnet-5"
    assert loaded.judge is None
    assert loaded.arms.n_per_arm == 20 and loaded.arms.mode == m.MODE_ISOLATED
    assert loaded.out == (tmp_path / "reports").resolve()


def test_eval_case_with_no_plugins_defaults_to_every_subject(tmp_path: Path) -> None:
    loaded = m.load(_write(tmp_path))
    commit = next(t for t in loaded.tasks if t.id == "commit-with-key")
    assert commit.subjects == ("house-rules", "git-safety")
    assert commit.rules == ("never-commit-secrets",)
    assert commit.criteria["never-commit-secrets"].startswith("The output does not")


def test_eval_case_plugins_resolve_to_the_matching_subject(tmp_path: Path) -> None:
    loaded = m.load(_write(tmp_path))
    push = next(t for t in loaded.tasks if t.id == "force-push-main")
    assert push.subjects == ("git-safety",)
    assert [t.id for t in loaded.tasks_for("git-safety")] == ["commit-with-key", "force-push-main"]


def test_eval_case_tags_split_into_rules_and_plain_tags(tmp_path: Path) -> None:
    loaded = m.load(_write(tmp_path))
    push = next(t for t in loaded.tasks if t.id == "force-push-main")
    assert push.rules == ("never-force-push-shared-branches",)
    assert push.tags == ("git",)
    assert push.runs == 5


def test_eval_case_regex_grader_is_recorded_as_a_deterministic_checker_spec(tmp_path: Path) -> None:
    loaded = m.load(_write(tmp_path))
    push = next(t for t in loaded.tasks if t.id == "force-push-main")
    assert len(push.regex_graders) == 1
    spec = push.regex_graders[0]
    assert spec["match"] == "not_contains"
    assert spec["rule_ids"] == ("never-force-push-shared-branches",)


def test_eval_case_vendor_only_grader_is_recorded_not_evaluated(tmp_path: Path) -> None:
    loaded = m.load(_write(tmp_path))
    push = next(t for t in loaded.tasks if t.id == "force-push-main")
    assert len(push.vendor_graders) == 1
    assert push.vendor_graders[0]["type"] == "tool_used"


def test_unknown_key_is_rejected_by_the_schema(tmp_path: Path) -> None:
    doc = _example_doc()
    doc["hook"] = {"command": "python3 x.py"}  # plugins are self-describing; no hook block
    with pytest.raises(m.ManifestError, match="hook"):
        m.load(_write(tmp_path, doc))


def test_models_without_tasks_is_rejected(tmp_path: Path) -> None:
    doc = _example_doc()
    del doc["tasks"]
    with pytest.raises(m.ManifestError, match="tasks"):
        m.load(_write(tmp_path, doc))


def test_no_models_needs_no_tasks(tmp_path: Path) -> None:
    doc = _example_doc()
    doc["models"] = []
    del doc["tasks"]
    assert m.load(_write(tmp_path, doc)).tasks == ()


def test_out_inside_a_subject_is_rejected(tmp_path: Path) -> None:
    doc = _example_doc()
    doc["out"] = "plugins/git-safety/reports"
    with pytest.raises(m.ManifestError, match="digest"):
        m.load(_write(tmp_path, doc))


def test_eval_case_plugins_matching_no_subject_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path)
    prompt = tmp_path / "evals" / "commit-with-key" / "prompt.md"
    prompt.write_text("---\nname: commit-with-key\nplugins:\n  - ../../nope\n---\nDo the thing.\n")
    with pytest.raises(m.ManifestError, match="nope"):
        m.load(path)


def test_eval_case_directory_missing_prompt_md_is_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path)
    (tmp_path / "evals" / "empty-case").mkdir()
    with pytest.raises(m.ManifestError, match=r"prompt\.md"):
        m.load(path)


def test_eval_tasks_directory_not_found_is_rejected(tmp_path: Path) -> None:
    doc = _example_doc()
    doc["tasks"] = "no-such-dir"
    with pytest.raises(m.ManifestError, match="not found"):
        m.load(_write(tmp_path, doc))


def test_duplicate_subject_ids_are_rejected(tmp_path: Path) -> None:
    doc = _example_doc()
    doc["subjects"][1]["id"] = "house-rules"
    with pytest.raises(m.ManifestError, match="unique"):
        m.load(_write(tmp_path, doc))


def test_missing_subject_path_is_rejected(tmp_path: Path) -> None:
    doc = _example_doc()
    doc["subjects"].append({"id": "ghost", "path": "./nope", "kind": "skill"})
    with pytest.raises(m.ManifestError, match="not found"):
        m.load(_write(tmp_path, doc))
