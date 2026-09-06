"""Rule extraction keeps directives, drops prose and code, and stays traceable to its line."""

from context_report.efficacy.rules import (
    SKIP_NOT_DIRECTIVE,
    SKIP_TOO_SHORT,
    Rule,
    discover,
    extract,
    extract_all,
    is_directive,
    slug,
)

SAMPLE = """# Project

This file explains how the project is laid out for new contributors.

## Conventions

- Always use constructor injection
- Never commit directly to main
- The API lives in `src/api/`

```python
# always use tabs here
print("this is code, not a rule")
```

| column | value |
|---|---|
| never | a table row |

<!-- always ignore html comments -->

> quoted prose that says you must never do this

Use 2-space indentation.
"""


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_extracts_directive_bullets(tmp_path):
    rules = extract(_write(tmp_path, "CLAUDE.md", SAMPLE)).rules
    texts = [r.text for r in rules]
    assert "Always use constructor injection" in texts
    assert "Never commit directly to main" in texts
    assert "Use 2-space indentation." in texts


def test_skips_code_headings_tables_comments_and_quotes(tmp_path):
    rules = extract(_write(tmp_path, "CLAUDE.md", SAMPLE)).rules
    texts = " | ".join(r.text for r in rules)
    assert "print(" not in texts
    assert "# Project" not in texts
    assert "a table row" not in texts
    assert "html comments" not in texts
    assert "quoted prose" not in texts


def test_descriptive_prose_is_not_a_rule(tmp_path):
    rules = extract(_write(tmp_path, "CLAUDE.md", SAMPLE)).rules
    assert all("explains how the project" not in r.text for r in rules)
    assert all("The API lives in" not in r.text for r in rules)


def test_ids_carry_file_and_line(tmp_path):
    rules = extract(_write(tmp_path, "CLAUDE.md", SAMPLE)).rules
    first = rules[0]
    assert first.id == slug(first.text), "the id is the rule's own words"
    assert first.line >= 1 and first.source.endswith("CLAUDE.md")
    assert SAMPLE.splitlines()[first.line - 1].endswith(first.text)


def test_inline_formatting_is_stripped(tmp_path):
    path = _write(tmp_path, "AGENTS.md", "- **Never** use `eval` in this repo\n")
    assert extract(path).rules[0].text == "Never use eval in this repo"


def test_length_bounds_reject_fragments_and_paragraphs(tmp_path):
    text = "- use it\n- " + ("always do the thing " * 30) + "\n"
    assert extract(_write(tmp_path, "CLAUDE.md", text)).rules == []


def test_discover_finds_known_filenames(tmp_path):
    _write(tmp_path, "CLAUDE.md", "- always test\n")
    _write(tmp_path, ".cursorrules", "never push to main\n")
    _write(tmp_path, "README.md", "- always ignored\n")
    found = {p.name for p in discover(tmp_path)}
    assert found == {"CLAUDE.md", ".cursorrules"}


def test_extract_all_keeps_source_order(tmp_path):
    a = _write(tmp_path, "CLAUDE.md", "- always run tests\n")
    b = _write(tmp_path, "AGENTS.md", "- never skip review\n")
    rules = extract_all([a, b]).rules
    assert [r.source for r in rules] == [str(a), str(b)]
    assert all(isinstance(r, Rule) for r in rules)


def test_is_directive_separates_instruction_from_description():
    assert is_directive("never use field injection")
    assert is_directive("Prefer immutability by default")
    assert is_directive("run npm test before committing")
    assert not is_directive("this project is a policy engine for agents")
    assert not is_directive("the handlers live under src/api/handlers")


def test_skips_are_counted_not_silent(tmp_path):
    text = "\n".join(
        [
            "This file explains how the project is laid out for new contributors.",
            "",
            "- ok",
            "",
            "- Never commit to main",
        ]
    )
    found = extract(_write(tmp_path, "CLAUDE.md", text))
    assert [r.text for r in found.rules] == ["Never commit to main"]
    assert sum(found.skipped.values()) == 2
    assert set(found.skipped) == {SKIP_TOO_SHORT, SKIP_NOT_DIRECTIVE}


def test_a_wrapped_bullet_is_one_rule(tmp_path):
    text = (
        "- Never use field injection; prefer constructor injection\n  with Lombok's annotation.\n"
    )
    rules = extract(_write(tmp_path, "CLAUDE.md", text)).rules
    assert len(rules) == 1
    assert rules[0].text.endswith("annotation.")
    assert rules[0].line == 1
