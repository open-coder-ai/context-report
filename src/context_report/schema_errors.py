"""JSON Schema error formatting shared by every `validate()` in this package."""

from __future__ import annotations

from collections.abc import Iterable

from jsonschema.exceptions import ValidationError

ROOT = "(root)"


def error_path(error: ValidationError) -> str:
    """JSON-pointer-style path to the failing field; the stable `ROOT` marker at the top level."""
    return "/".join(str(p) for p in error.absolute_path) or ROOT


def format_error(error: ValidationError) -> str:
    """`path: message`; a `const` failure also names the expected and offending values."""
    message = error.message
    if error.validator == "const":
        message = f"expected {error.validator_value!r}, got {error.instance!r}"
    return f"{error_path(error)}: {message}"


def format_errors(errors: Iterable[ValidationError]) -> list[str]:
    """Sort by path and format every error into the `path: message` shape."""
    return [format_error(e) for e in sorted(errors, key=lambda e: list(e.absolute_path))]
