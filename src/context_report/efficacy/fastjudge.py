"""Deterministic fast-path judge: check machine-checkable rules by code, not by an LLM call."""

from __future__ import annotations

import ast
import re
from typing import ClassVar, Protocol

from context_report.efficacy.core import Judge

_FENCE = re.compile(r"```[a-zA-Z0-9_+-]*\n(.*?)```", re.DOTALL)


def code_of(output: str) -> str:
    """Fenced code blocks, so we judge code and not prose; falls back to all text."""
    blocks = _FENCE.findall(output)
    return "\n".join(blocks) if blocks else output


class CannotJudgeError(Exception):
    """This checker cannot decide this output — fall back to the LLM judge."""


class Checker(Protocol):
    name: str

    def applies(self, rule: str) -> bool: ...
    def obeys(self, rule: str, code: str) -> bool: ...


class NoAnyType:
    name = "no-any-type"

    def applies(self, rule: str) -> bool:
        return bool(re.search(r"(?i)\bany\b", rule)) and "type" in rule.lower()

    def obeys(self, rule: str, code: str) -> bool:
        return not re.search(r"(?i):\s*any\b|<any>|\bas any\b", code)


class ForbiddenCall:
    name = "forbidden-call"
    _CALLS: ClassVar[dict[str, str]] = {
        "print": r"\bprint\s*\(",
        "console.log": r"console\.log\s*\(",
    }

    def _target(self, rule: str) -> str | None:
        m = re.search(r"(?i)\bno\s+(print|console\.log)", rule)
        return m.group(1).lower() if m else None

    def applies(self, rule: str) -> bool:
        return self._target(rule) is not None

    def obeys(self, rule: str, code: str) -> bool:
        target = self._target(rule)
        if target is None:  # pragma: no cover - guarded by applies()
            raise CannotJudgeError
        return not re.search(self._CALLS[target], code)


class TabsIndent:
    name = "tabs-indent"

    def applies(self, rule: str) -> bool:
        return bool(re.search(r"(?i)\btabs?\b", rule))

    def obeys(self, rule: str, code: str) -> bool:
        indented = [ln for ln in code.splitlines() if ln[:1] in (" ", "\t")]
        if not indented:
            raise CannotJudgeError
        return all(ln.startswith("\t") for ln in indented)


class NoElseAfterReturn:
    name = "no-else-after-return"

    def applies(self, rule: str) -> bool:
        return bool(re.search(r"(?i)else after (a )?return|guard clause|early return", rule))

    def obeys(self, rule: str, code: str) -> bool:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            raise CannotJudgeError from exc
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.If)
                and node.orelse
                and node.body
                and isinstance(node.body[-1], ast.Return)
            ):
                return False
        return True


_REGEX_GRADER_FLAGS = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL, "x": re.VERBOSE}


def _regex_grader_flags(letters: str) -> re.RegexFlag:
    """`"im"` -> `re.IGNORECASE | re.MULTILINE`; an unknown letter is a loud error, not a no-op."""
    value = re.RegexFlag(0)
    for letter in letters:
        if letter not in _REGEX_GRADER_FLAGS:
            raise ValueError(f"unknown regex grader flag {letter!r}")
        value |= _REGEX_GRADER_FLAGS[letter]
    return value


class GraderRegex:
    """A `claude plugin eval` `regex` grader (`target: last_message`), compiled to a `Checker`.

    Built by `context_report.run.evalcases.checkers_for` from the case's own `pattern`, `flags`
    and `match` (`contains` / `not_contains` / `count:N`) grader fields. `rule_ids` is which rule
    ids this grader binds to -- its own `rule:` field, or the case's `rule:` tags; empty means it
    was bound to none of those, so it applies to every rule (mirrors a task with no `rules`).

    Unlike `DEFAULT_CHECKERS`, which read the rule's *text*, `applies`/`obeys` here expect
    ``rule`` to be a rule *id* -- see `evalcases.checkers_for` for why wiring this in needs the
    caller to pass ids, not `rule.text`, through `grade()`.
    """

    name = "eval-case-regex"
    full_output = True  # a last_message grader reads the whole reply, not only its code fences

    def __init__(
        self,
        pattern: str,
        flags: str,
        match: str,
        rule_ids: tuple[str, ...] = (),
        rule_texts: tuple[str, ...] = (),
    ):
        self._regex = re.compile(pattern, _regex_grader_flags(flags))
        self.match = match
        self.rule_ids = rule_ids
        self.rule_texts = rule_texts  # measure() hands checkers the rule text, not its id

    def applies(self, rule: str) -> bool:
        bound = self.rule_ids or self.rule_texts
        return not bound or rule in self.rule_ids or rule in self.rule_texts

    def obeys(self, rule: str, code: str) -> bool:
        """`code` here is the case's whole last-message output, not just its code fences."""
        count = len(self._regex.findall(code))
        if self.match == "contains":
            return count > 0
        if self.match == "not_contains":
            return count == 0
        if self.match.startswith("count:"):
            return count == int(self.match.split(":", 1)[1])
        raise ValueError(f"unknown regex grader match mode: {self.match!r}")


DEFAULT_CHECKERS: tuple[Checker, ...] = (
    NoAnyType(),
    ForbiddenCall(),
    TabsIndent(),
    NoElseAfterReturn(),
)


def _restates(rule: str, criterion: str) -> bool:
    """True when the case's criterion says nothing the rule does not already say."""
    return not criterion.strip() or criterion.strip() == rule.strip()


class FastPathJudge:
    """Try deterministic checkers first; fall back to an LLM judge for fuzzy rules.

    A checker decides a question about the *rule*. When a case carries its own criterion, that
    is a different and narrower question, so the fast path steps aside rather than answer
    confidently for the wrong one -- a free wrong verdict is worth less than a paid right one.
    """

    def __init__(self, fallback: Judge, checkers: tuple[Checker, ...] = DEFAULT_CHECKERS):
        self.fallback = fallback
        self.checkers = checkers
        self.last_source = ""

    def obeys(self, rule: str, task: str, output: str, criterion: str) -> bool:
        code = code_of(output)
        if _restates(rule, criterion):
            for checker in self.checkers:
                if checker.applies(rule):
                    try:
                        text = output if getattr(checker, "full_output", False) else code
                        verdict = checker.obeys(rule, text)
                    except CannotJudgeError:
                        continue
                    self.last_source = checker.name
                    return verdict
        self.last_source = "llm"
        return self.fallback.obeys(rule, task, output, criterion)
