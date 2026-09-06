"""The library surface: every name in `context_report.__all__` is importable and usable."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import context_report
from context_report.run.manifest import load as manifest_load
from context_report.run.runner import run as runner_run

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = json.loads(
    (ROOT / "spec/attestation/v0.1/examples/plugin-copilot.json").read_text(encoding="utf-8")
)


def test_all_lists_the_intended_surface():
    assert context_report.__all__ == [
        "__version__",
        "history_markdown",
        "load_manifest",
        "produce_statement",
        "render_history",
        "render_table",
        "resolve_run_dir",
        "rule_history_markdown",
        "run",
        "validate",
        "verify",
    ]


def test_every_name_in_all_is_present_and_importable():
    for name in context_report.__all__:
        assert hasattr(context_report, name), f"{name} is in __all__ but not on the module"


def test_every_export_except_the_version_string_is_callable():
    for name in context_report.__all__:
        if name == "__version__":
            continue
        assert callable(getattr(context_report, name)), f"{name} is not callable"


def test_version_is_a_nonempty_string():
    assert isinstance(context_report.__version__, str)
    assert context_report.__version__


def test_validate_the_worked_example_has_no_schema_errors():
    assert context_report.validate(EXAMPLE) == []


def test_verify_the_worked_example_is_ok():
    result = context_report.verify(EXAMPLE)
    assert result.ok is True
    assert result.schema_errors == []


def test_produce_statement_signature_is_unchanged():
    params = inspect.signature(context_report.produce_statement).parameters
    assert params["subject"].kind is inspect.Parameter.KEYWORD_ONLY
    assert "subject_kind" in params
    assert "target" in params


def test_load_manifest_is_run_manifest_load():
    assert context_report.load_manifest is manifest_load


def test_run_is_run_runner_run():
    assert context_report.run is runner_run
