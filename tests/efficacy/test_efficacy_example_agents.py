"""The shipped example has a known answer; pin it so the fixture cannot drift unnoticed."""

from pathlib import Path

from context_report.efficacy.fastjudge import DEFAULT_CHECKERS
from context_report.efficacy.rules import SKIP_NOT_DIRECTIVE, SKIP_TOO_LONG, SKIP_TOO_SHORT, extract

EXAMPLE = Path(__file__).resolve().parent / "fixtures" / "examples" / "AGENTS.md"


def _found():
    return extract(EXAMPLE)


def test_every_skip_reason_is_exercised():
    assert _found().skipped == {SKIP_NOT_DIRECTIVE: 2, SKIP_TOO_LONG: 1, SKIP_TOO_SHORT: 1}


def test_the_wrapped_bullet_is_one_rule():
    joined = [r for r in _found().rules if r.text.startswith("Never use field injection")]
    assert len(joined) == 1
    assert joined[0].text.endswith("without standing up a container")


def test_half_the_rules_need_no_model_call():
    def checker(text):
        return next((c.name for c in DEFAULT_CHECKERS if c.applies(text)), "llm")

    names = [checker(r.text) for r in _found().rules]
    assert sorted(n for n in names if n != "llm") == [
        "forbidden-call",
        "forbidden-call",
        "no-any-type",
        "no-else-after-return",
        "tabs-indent",
    ]
    assert names.count("llm") == 5
