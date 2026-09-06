"""A manifest is validated and resolved before anything runs; every mistake is named."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from context_report.run import manifest as m

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "spec" / "run" / "v0.1" / "examples"


def _write(tmp_path: Path, doc: dict, tasks: dict | None = None) -> Path:
    (tmp_path / "AGENTS.md").write_text("- Never commit secrets.\n")
    (tmp_path / "plugins" / "git-safety").mkdir(parents=True)
    (tmp_path / "plugins" / "git-safety" / "SKILL.md").write_text("# git safety\n")
    if tasks is not None:
        (tmp_path / "tasks.json").write_text(json.dumps(tasks))
    path = tmp_path / "run.json"
    path.write_text(json.dumps(doc))
    return path


def _example_docs() -> tuple[dict, dict]:
    return (
        json.loads((EXAMPLES / "run.json").read_text()),
        json.loads((EXAMPLES / "tasks.json").read_text()),
    )


def test_package_copy_of_the_schema_is_byte_identical() -> None:
    spec = (ROOT / "spec" / "run" / "v0.1" / "schema.json").read_bytes()
    pkg = (ROOT / "src" / "context_report" / "data" / "run-v0.1.schema.json").read_bytes()
    assert spec == pkg


def test_worked_example_loads_and_resolves(tmp_path: Path) -> None:
    doc, tasks = _example_docs()
    path = _write(tmp_path, doc, tasks)
    loaded = m.load(path)
    assert [s.id for s in loaded.subjects] == ["house-rules", "git-safety"]
    assert loaded.subjects[0].path == (tmp_path / "AGENTS.md").resolve()
    assert loaded.target.client_version == "2.1.0"
    assert next(x.slug for x in loaded.models) == "anthropic--claude-sonnet-5"
    assert loaded.judge is None
    assert loaded.arms.n_per_arm == 20 and loaded.arms.mode == m.MODE_ISOLATED
    assert loaded.out == (tmp_path / "reports").resolve()


def test_task_defaults_to_every_subject_and_every_rule(tmp_path: Path) -> None:
    doc, tasks = _example_docs()
    loaded = m.load(_write(tmp_path, doc, tasks))
    tidy = next(t for t in loaded.tasks if t.id == "tidy-and-ship")
    assert tidy.subjects == ("house-rules", "git-safety") and tidy.rules == ()
    assert [t.id for t in loaded.tasks_for("git-safety")] == ["force-push-main", "tidy-and-ship"]
    key = next(t for t in loaded.tasks if t.id == "commit-with-key")
    assert key.criteria["never-commit-secrets"].startswith("The output does not")


def test_unknown_key_is_rejected_by_the_schema(tmp_path: Path) -> None:
    doc, tasks = _example_docs()
    doc["hook"] = {"command": "python3 x.py"}  # plugins are self-describing; no hook block
    with pytest.raises(m.ManifestError, match="hook"):
        m.load(_write(tmp_path, doc, tasks))


def test_models_without_tasks_is_rejected(tmp_path: Path) -> None:
    doc, _ = _example_docs()
    del doc["tasks"]
    with pytest.raises(m.ManifestError, match="tasks"):
        m.load(_write(tmp_path, doc))


def test_no_models_needs_no_tasks(tmp_path: Path) -> None:
    doc, _ = _example_docs()
    doc["models"] = []
    del doc["tasks"]
    assert m.load(_write(tmp_path, doc)).tasks == ()


def test_out_inside_a_subject_is_rejected(tmp_path: Path) -> None:
    doc, tasks = _example_docs()
    doc["out"] = "plugins/git-safety/reports"
    with pytest.raises(m.ManifestError, match="digest"):
        m.load(_write(tmp_path, doc, tasks))


def test_task_naming_unknown_subject_is_rejected(tmp_path: Path) -> None:
    doc, tasks = _example_docs()
    tasks["tasks"][0]["subjects"] = ["nope"]
    with pytest.raises(m.ManifestError, match="nope"):
        m.load(_write(tmp_path, doc, tasks))


def test_duplicate_subject_ids_are_rejected(tmp_path: Path) -> None:
    doc, tasks = _example_docs()
    doc["subjects"][1]["id"] = "house-rules"
    with pytest.raises(m.ManifestError, match="unique"):
        m.load(_write(tmp_path, doc, tasks))


def test_missing_subject_path_is_rejected(tmp_path: Path) -> None:
    doc, tasks = _example_docs()
    doc["subjects"].append({"id": "ghost", "path": "./nope", "kind": "skill"})
    with pytest.raises(m.ManifestError, match="not found"):
        m.load(_write(tmp_path, doc, tasks))
