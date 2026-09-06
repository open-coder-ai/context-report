"""Each deterministic checker judges by code, and the judge falls back only for fuzzy rules."""

from context_report.efficacy.fastjudge import FastPathJudge, code_of


class SpyJudge:
    """Stand-in LLM judge: records if it was called, with what criterion, and returns a verdict."""

    def __init__(self, verdict=True):
        self.verdict = verdict
        self.calls = 0
        self.criteria = []

    def obeys(self, rule, task, output, criterion):
        self.calls += 1
        self.criteria.append(criterion)
        return self.verdict


def judge():
    return FastPathJudge(SpyJudge())


def test_code_of_extracts_fences():
    assert code_of("blah\n```python\nx=1\n```\nmore").strip() == "x=1"
    assert code_of("no fence here") == "no fence here"


def test_no_any_type():
    j = judge()
    assert j.obeys("never use the any type", "t", "```ts\nlet x: any = 1\n```", "") is False
    assert j.obeys("never use the any type", "t", "```ts\nlet x: number = 1\n```", "") is True
    assert j.last_source == "no-any-type" and j.fallback.calls == 0


def test_forbidden_call():
    j = judge()
    assert j.obeys("no print statements", "t", "```py\nprint('x')\n```", "") is False
    assert j.obeys("no print statements", "t", "```py\nlog('x')\n```", "") is True
    assert j.obeys("no console.log", "t", "```js\nconsole.log(1)\n```", "") is False
    assert j.fallback.calls == 0


def test_tabs_indent():
    j = judge()
    assert j.obeys("use tabs for indentation", "t", "def f():\n\treturn 1\n", "") is True
    assert j.obeys("use tabs for indentation", "t", "def f():\n    return 1\n", "") is False
    assert j.last_source == "tabs-indent"


def test_tabs_falls_back_when_nothing_indented():
    j = judge()
    j.obeys("use tabs for indentation", "t", "x = 1\n", "")
    assert j.last_source == "llm" and j.fallback.calls == 1


def test_no_else_after_return_ast():
    j = judge()
    bad = "```py\ndef f(x):\n    if x:\n        return 1\n    else:\n        return 2\n```"
    good = "```py\ndef f(x):\n    if x:\n        return 1\n    return 2\n```"
    assert j.obeys("use early returns, no else after a return", "t", bad, "") is False
    assert j.obeys("use early returns, no else after a return", "t", good, "") is True
    assert j.last_source == "no-else-after-return" and j.fallback.calls == 0


def test_no_else_after_return_falls_back_on_unparseable():
    j = judge()
    j.obeys("guard clause", "t", "```py\ndef f( : broken\n```", "")
    assert j.last_source == "llm" and j.fallback.calls == 1


def test_fuzzy_rule_uses_the_llm_fallback():
    j = judge()
    assert j.obeys("write clear, descriptive variable names", "t", "x=1", "") is True
    assert j.last_source == "llm" and j.fallback.calls == 1


def test_a_criterion_that_restates_the_rule_still_takes_the_fast_path():
    """Generated scenarios set rule_applies to the rule itself; that must not cost a model call."""
    j = judge()
    rule = "never use the any type"
    assert j.obeys(rule, "t", "```ts\nlet x: any = 1\n```", rule) is False
    assert j.last_source == "no-any-type" and j.fallback.calls == 0


def test_a_case_with_its_own_criterion_is_not_decided_by_a_checker():
    """A checker answers a question about the rule; the case is asking a narrower one."""
    j = judge()
    j.obeys("never use the any type", "t", "```ts\nlet x: any = 1\n```", "declares an interface")
    assert j.last_source == "llm", "the deterministic checker answered the wrong question"
    assert j.fallback.calls == 1


def test_the_criterion_reaches_the_fallback_verbatim():
    j = judge()
    j.obeys("some fuzzy rule", "t", "out", "refuses and names the safe alternative")
    assert j.fallback.criteria == ["refuses and names the safe alternative"]
