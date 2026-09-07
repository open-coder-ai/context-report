"""Property-based tests: the parsers and id derivations hold for any input, not only examples."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from context_report.efficacy import rules
from context_report.rows import input_hash
from context_report.run import evalcases, layout

SLUG_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789-")


@settings(max_examples=200, deadline=None)
@given(st.text())
def test_slug_is_a_stable_id_of_bounded_shape(text: str) -> None:
    """Whatever the rule says, its id is short, lowercase, hyphenated, and re-slugs to itself."""
    out = rules.slug(text)
    assert out and set(out) <= SLUG_CHARS
    assert len(out) <= rules._SLUG_CHARS
    assert not out.startswith("-") and not out.endswith("-")
    assert rules.slug(out) == out


@settings(max_examples=100, deadline=None)
@given(st.text())
def test_extract_never_raises_and_ids_are_unique(tmp_path_factory: pytest.TempPathFactory, text):
    """Any file is either rules or skips; no crash, and ids never collide within one file."""
    path = tmp_path_factory.mktemp("subject") / "AGENTS.md"
    path.write_text(text, encoding="utf-8")
    found = rules.extract(path)
    ids = [r.id for r in found.rules]
    assert len(ids) == len(set(ids))
    assert all(set(i) <= SLUG_CHARS for i in ids)
    assert all(c.id and set(c.id) <= SLUG_CHARS for c in found.candidates)


@settings(max_examples=100, deadline=None)
@given(st.lists(st.text(), max_size=6), st.lists(st.text(), max_size=6))
def test_input_hash_is_deterministic_and_order_sensitive(a: list[str], b: list[str]) -> None:
    assert input_hash(*a) == input_hash(*a)
    if a != b:
        assert input_hash(*a) != input_hash(*b)


_key = st.from_regex(r"\A[a-z][a-z0-9_]{0,15}\Z")
# Plain YAML scalars only: letters, digits, spaces and a few safe marks, starting with a letter,
# so the property is about the frontmatter split, not about YAML's own scalar grammar.
_value = st.from_regex(r"\A[A-Za-z][A-Za-z0-9 _.-]{0,39}\Z")


@settings(max_examples=100, deadline=None)
@given(
    st.dictionaries(_key, _value, max_size=4),
    st.text(max_size=200).filter(lambda b: "\r" not in b),  # read_text normalises newlines
)
def test_frontmatter_round_trips_meta_and_body(tmp_path_factory, meta: dict, body: str) -> None:
    """A prompt.md written with a YAML mapping and any body reads back as that mapping and body."""
    path = tmp_path_factory.mktemp("case") / "prompt.md"
    yaml_lines = "\n".join(f"{k}: {v}" for k, v in meta.items())
    path.write_text(f"---\n{yaml_lines}\n---\n{body}", encoding="utf-8")
    parsed_meta, parsed_body = evalcases._frontmatter(path)
    assert set(parsed_meta) == set(meta)
    assert parsed_body == body.strip()


@settings(max_examples=100, deadline=None)
@given(
    st.lists(
        st.fixed_dictionaries(
            {
                "runId": st.from_regex(r"\A[0-9]{8}T[0-9]{6}Z\Z"),
                "startedOn": st.just("2026-09-07T00:00:00Z"),
                "finishedOn": st.just("2026-09-07T00:01:00Z"),
                "rows": st.lists(
                    st.fixed_dictionaries(
                        {
                            "subject": st.from_regex(r"\A[a-z][a-z0-9-]{0,10}\Z"),
                            "model": st.from_regex(r"\A[a-z]+/[a-z0-9.-]{1,12}\Z"),
                            "result": st.sampled_from(
                                ["PASSED", "WARNED", "FAILED", "NotAvailable"]
                            ),
                            "estimate": st.none()
                            | st.tuples(st.floats(-1, 1), st.floats(-1, 1), st.floats(-1, 1)).map(
                                list
                            ),
                        }
                    ),
                    max_size=4,
                ),
            }
        ),
        max_size=4,
        unique_by=lambda e: e["runId"],
    )
)
def test_history_table_names_every_run_and_pair(index: list[dict]) -> None:
    table = layout.history_markdown(index)
    for entry in index:
        assert entry["runId"] in table
        for row in entry["rows"]:
            assert row["subject"] in table and row["model"] in table


_SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "render_pages.py"


@settings(max_examples=100, deadline=None)
@given(st.from_regex(r"\A[A-Za-z0-9_./-]{1,30}\Z"))
def test_rendered_links_to_markdown_point_at_pages(target: str) -> None:
    """Every `.md` link becomes a `.html` link; links to anything else are untouched."""
    pytest.importorskip("markdown")
    spec = importlib.util.spec_from_file_location("render_pages", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    html = module.render_markdown(f"[a]({target}.md) [b]({target}.json)", "t")
    assert f'href="{target}.html"' in html
    assert f'href="{target}.json"' in html
    assert f'href="{target}.md"' not in html
