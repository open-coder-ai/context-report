"""The predicate URI must resolve and every published copy of it must agree."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from context_report.rows import PREDICATE_TYPE

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "spec/attestation/v0.1/schema.json"
EXAMPLE_PATH = ROOT / "spec/attestation/v0.1/examples/plugin-copilot.json"
PAGES_WORKFLOW = ROOT / ".github/workflows/pages.yml"
SPEC_INDEX = ROOT / "spec/index.md"
V01_INDEX = ROOT / "spec/attestation/v0.1/index.md"

# W1 is producing these concurrently; the two index pages link to them by name
# even though they do not exist in this worktree yet.
EXPECTED_NOT_YET_PRESENT = {"README.md", "attributes.md"}

LINK_RE = re.compile(r"\]\(([^)]+)\)")


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def test_schema_id_matches_expected_hosted_path():
    expected = "https://open-coder-ai.github.io/context-report/attestation/v0.1/schema.json"
    assert _schema()["$id"] == expected


def test_predicate_type_const_matches_rows_constant():
    schema_predicate_type = _schema()["properties"]["predicateType"]["const"]
    assert schema_predicate_type == PREDICATE_TYPE
    assert PREDICATE_TYPE == "https://open-coder-ai.github.io/context-report/attestation/v0.1"


def test_schema_id_is_discoverable_from_the_predicate_type():
    """$id == predicateType + "/schema.json", so a verifier can find the schema from the type."""
    assert _schema()["$id"] == PREDICATE_TYPE + "/schema.json"


def test_example_predicate_type_matches():
    example = json.loads(EXAMPLE_PATH.read_text())
    assert example["predicateType"] == PREDICATE_TYPE


def test_pyproject_specification_url_starts_with_predicate_type():
    # tomllib is 3.11+; this project supports 3.10, so read the one key by regex.
    text = (ROOT / "pyproject.toml").read_text()
    match = re.search(r'^Specification\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, "pyproject.toml has no [project.urls] Specification entry"
    assert match.group(1).startswith(PREDICATE_TYPE)


@pytest.mark.parametrize("path", [SPEC_INDEX, V01_INDEX])
def test_index_pages_contain_the_predicate_type(path):
    assert PREDICATE_TYPE in path.read_text()


def test_pages_workflow_publishes_the_spec_directory():
    """Pages serves the rendered spec: the renderer reads `spec`, the upload ships its output."""
    workflow_text = PAGES_WORKFLOW.read_text()
    assert re.search(r"render_pages\.py spec _site\s*$", workflow_text, re.MULTILINE)
    assert re.search(r"^\s*path:\s*_site\s*$", workflow_text, re.MULTILINE)


@pytest.mark.parametrize("path", [SPEC_INDEX, V01_INDEX])
def test_relative_links_point_at_files_that_exist(path):
    base = path.parent
    for target in LINK_RE.findall(path.read_text()):
        if target.startswith(("http://", "https://", "#")):
            continue
        if Path(target).name in EXPECTED_NOT_YET_PRESENT:
            continue
        assert (base / target).exists(), f"{path}: broken link {target!r}"
