"""The Pages build renders `spec/` so its root and every spec page serve as HTML, not a 404."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("markdown", reason="the Pages renderer needs the dev extra's markdown")

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "render_pages.py"


def _module():
    spec = importlib.util.spec_from_file_location("render_pages", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_spec_renders_with_an_index_and_rewritten_links(tmp_path: Path) -> None:
    out = tmp_path / "_site"
    written = _module().render_tree(ROOT / "spec", out)
    assert (out / "index.html").is_file(), "the Pages root must be a page, not a 404"
    assert (out / "attestation" / "v0.1" / "index.html").is_file()
    assert (out / "run" / "v0.1" / "index.html").is_file()
    root = (out / "index.html").read_text(encoding="utf-8")
    assert "<title>context-report</title>" in root
    assert 'href="attestation/v0.1/"' in root
    assert '.md"' not in root, "links to Markdown files point at their rendered pages"
    assert (out / "attestation" / "v0.1" / "README.html").is_file()
    # Everything that is not Markdown is served byte for byte: the schema URL is the predicate type.
    schema = "attestation/v0.1/schema.json"
    assert (out / schema).read_bytes() == (ROOT / "spec" / schema).read_bytes()
    assert (out / "index.md").is_file(), "the Markdown source stays published beside its page"
    assert len(written) == len(list((ROOT / "spec").rglob("*.md")))
