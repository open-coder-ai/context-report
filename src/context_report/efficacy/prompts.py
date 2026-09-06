"""Load prompt templates from the package data dir and fill their __TOKEN__ placeholders."""

from __future__ import annotations

import re
from importlib.resources import files

_PLACEHOLDER = re.compile(r"__[A-Z0-9_]+__")
_UNKNOWN_PLACEHOLDER = "template {name!r} has no placeholder {placeholder}"
_UNFILLED_PLACEHOLDER = "template {name!r} left {placeholders} unfilled"


def template(name: str) -> str:
    """Raw template text as committed, placeholders intact."""
    path = files("context_report.data") / "efficacy" / "prompts" / f"{name}.md"
    return path.read_text(encoding="utf-8")


def tokens_in(name: str) -> set[str]:
    """Every placeholder the template carries."""
    return set(_PLACEHOLDER.findall(template(name)))


def render(name: str, **values: str) -> str:
    """Fill every placeholder; unknown or unfilled tokens are errors, not silent output."""
    text = template(name)
    present = tokens_in(name)
    for key, value in values.items():
        placeholder = f"__{key.upper()}__"
        if placeholder not in present:
            raise KeyError(_UNKNOWN_PLACEHOLDER.format(name=name, placeholder=placeholder))
        text = text.replace(placeholder, value)
    leftover = _PLACEHOLDER.findall(text)
    if leftover:
        raise KeyError(_UNFILLED_PLACEHOLDER.format(name=name, placeholders=sorted(set(leftover))))
    return text
