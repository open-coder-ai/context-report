"""Hardening: manifest endpoints, hook paths, scratch cleanup, linked dirs, regex bound."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from context_report import rows
from context_report.efficacy.fastjudge import GraderRegex, GraderTimeoutError, _bounded_count
from context_report.produce.cost import injected_text_paths
from context_report.produce.discover import discover_hooks
from context_report.produce.reachability import reachability_row
from context_report.run import manifest as m
from context_report.statement import digest_path

_ALLOW = "import sys\nsys.stdin.read()\nsys.exit(0)\n"


def _manifest(tmp_path: Path, model: dict) -> Path:
    (tmp_path / "RULES.md").write_text("rules\n")
    doc = {
        "contextReportRun": "v0.1",
        "subjects": [{"id": "rules", "path": "./RULES.md", "kind": "instruction-file"}],
        "target": {"name": "claude_code", "clientVersion": "2.1.0"},
        "models": [{"provider": "openai-compatible", "id": "x", **model}],
        "tasks": {"tasks": [{"id": "t", "prompt": "p"}]},
        "arms": {"nPerArm": 2, "seed": 1, "mode": "isolated"},
        "judge": None,
        "out": "out",
    }
    (tmp_path / "run.json").write_text(json.dumps(doc))
    return tmp_path / "run.json"


@pytest.mark.parametrize(
    "model",
    [
        {"baseUrl": "http://evil.example/v1", "apiKeyEnv": "OPENAI_API_KEY"},
        {"baseUrl": "https://api.openai.com/v1", "apiKeyEnv": "GITHUB_TOKEN"},
    ],
)
def test_manifest_refuses_an_unsafe_endpoint_or_key_variable(tmp_path, model):
    with pytest.raises(m.ManifestError, match=r"baseUrl|apiKeyEnv"):
        m.load(_manifest(tmp_path, model))


def test_manifest_still_loads_a_local_server(tmp_path):
    loaded = m.load(_manifest(tmp_path, {"baseUrl": "http://localhost:11434/v1"}))
    assert loaded.models[0].base_url == "http://localhost:11434/v1"


def test_a_manifest_hooks_path_outside_the_subject_is_not_read(tmp_path):
    plugin = tmp_path / "p"
    (plugin / ".claude-plugin").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "hooks.json").write_text(
        json.dumps({"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "x"}]}]}})
    )
    for declared in ("../outside/hooks.json", str(outside / "hooks.json")):
        (plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps({"hooks": declared}))
        assert discover_hooks(plugin, "claude_code") == []


def test_a_manifest_hooks_path_through_a_link_that_leaves_the_subject_is_not_read(tmp_path):
    plugin = tmp_path / "p"
    (plugin / ".claude-plugin").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "hooks.json").write_text(
        json.dumps({"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "x"}]}]}})
    )
    (plugin / "link").symlink_to(outside, target_is_directory=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps({"hooks": "link/hooks.json"}))
    assert discover_hooks(plugin, "claude_code") == []


def test_cleanup_removes_only_the_scratch_dir_the_tool_made(tmp_path):
    (tmp_path / "gate.py").write_text(_ALLOW)
    keep = tmp_path / "_context_report_tmp" / "keep-me.txt"
    keep.parent.mkdir()
    keep.write_text("mine")
    row = reachability_row(f'python3 "{tmp_path}/gate.py"', tmp_path)
    assert row.result == rows.PASSED
    assert keep.read_text() == "mine"
    assert not (tmp_path / "_context_report_tmp" / "nested").exists()


def test_cleanup_removes_the_parent_it_created(tmp_path):
    (tmp_path / "gate.py").write_text(_ALLOW)
    reachability_row(f'python3 "{tmp_path}/gate.py"', tmp_path)
    assert not (tmp_path / "_context_report_tmp").exists()


def _escaping_link(tmp_path: Path) -> Path:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("one")
    subject = tmp_path / "plugin"
    subject.mkdir()
    (subject / "rules").symlink_to(outside, target_is_directory=True)
    return subject


def test_a_subject_with_a_directory_link_leaving_it_is_refused(tmp_path):
    subject = _escaping_link(tmp_path)
    with pytest.raises(ValueError, match="outside"):
        digest_path(subject)


def test_a_subject_with_a_file_link_leaving_it_is_refused(tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("one")
    subject = tmp_path / "plugin"
    subject.mkdir()
    (subject / "rules.md").symlink_to(outside)
    with pytest.raises(ValueError, match="outside"):
        digest_path(subject)


def test_links_that_stay_inside_the_subject_are_still_hashed(tmp_path):
    subject = tmp_path / "plugin"
    (subject / "real").mkdir(parents=True)
    (subject / "real" / "a.md").write_text("a")
    (subject / "rules").symlink_to(subject / "real", target_is_directory=True)
    first = digest_path(subject)
    (subject / "real" / "a.md").write_text("b")
    assert digest_path(subject) != first
    assert [p.name for p in injected_text_paths(subject, "plugin")] == ["a.md"]


def _never_answers(_conn, _pattern, _flags, _text):  # stands in for a pattern that never finishes
    time.sleep(60)


def test_a_regex_grader_that_never_finishes_is_stopped(monkeypatch):
    monkeypatch.setattr("context_report.efficacy.fastjudge.GRADER_TIMEOUT_S", 1.0)
    started = time.monotonic()
    with pytest.raises(GraderTimeoutError, match="regex"):
        _bounded_count("x", 0, "x", _target=_never_answers)
    assert time.monotonic() - started < 20


def test_a_regex_grader_still_answers_normally():
    grader = GraderRegex("all clear", "i", "contains")
    assert grader.obeys("r", "ALL CLEAR") is True
    assert GraderRegex("x", "", "count:2").obeys("r", "x x") is True
