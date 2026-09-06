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
                        verdict = checker.obeys(rule, code)
                    except CannotJudgeError:
                        continue
                    self.last_source = checker.name
                    return verdict
        self.last_source = "llm"
        return self.fallback.obeys(rule, task, output, criterion)
