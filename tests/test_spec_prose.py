"""Prose must not drift from schema.json: every field and attribute name has a home in both."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V01 = ROOT / "spec" / "attestation" / "v0.1"
SCHEMA = json.loads((V01 / "schema.json").read_text(encoding="utf-8"))
README = (V01 / "README.md").read_text(encoding="utf-8")
ATTRIBUTES_MD = (V01 / "attributes.md").read_text(encoding="utf-8")

SCHEMA_ATTRIBUTE_NAMES = set(SCHEMA["$defs"]["attributeName"]["anyOf"][0]["enum"])
HEADING_NAMES = set(re.findall(r"^## (\S+)$", ATTRIBUTES_MD, flags=re.MULTILINE))


def test_every_schema_attribute_has_a_heading() -> None:
    missing = SCHEMA_ATTRIBUTE_NAMES - HEADING_NAMES
    assert not missing, f"attributes.md is missing headings for: {sorted(missing)}"


def test_every_heading_is_a_schema_attribute() -> None:
    """No stale or invented attribute may linger in the registry once dropped from the schema."""
    extra = HEADING_NAMES - SCHEMA_ATTRIBUTE_NAMES
    assert not extra, f"attributes.md has headings for unknown attributes: {sorted(extra)}"


def test_every_predicate_field_is_documented() -> None:
    names = set(SCHEMA["$defs"]["predicate"]["properties"])
    missing = {n for n in names if n not in README}
    assert not missing, f"README.md never mentions predicate field(s): {sorted(missing)}"


def test_every_attribute_row_field_is_documented() -> None:
    names = set(SCHEMA["$defs"]["attribute"]["properties"])
    missing = {n for n in names if n not in README}
    assert not missing, f"README.md never mentions row field(s): {sorted(missing)}"


def test_required_phrases_are_present() -> None:
    for phrase in ("MUST NOT be read as a pass", "re-derivable", "claimed", "0.X"):
        assert phrase in README, f"README.md is missing required phrase: {phrase!r}"


APPLICABILITY = json.loads(
    (ROOT / "src" / "context_report" / "data" / "applicability-v0.1.json").read_text(
        encoding="utf-8"
    )
)["notApplicable"]
KINDS = set(SCHEMA["$defs"]["predicate"]["properties"]["subjectKind"]["enum"])


def _schema_not_applicable() -> dict[str, set[str]]:
    """The (kind -> excluded attributes) table as the predicate-level conditionals encode it."""
    table: dict[str, set[str]] = {k: set() for k in KINDS}
    for clause in SCHEMA["$defs"]["predicate"].get("allOf", []):
        kind = clause["if"]["properties"]["subjectKind"]["const"]
        inner = clause["then"]["properties"]["attributes"]["items"]
        assert inner["then"]["properties"]["result"]["const"] == "NotApplicable"
        table[kind] |= set(inner["if"]["properties"]["attribute"]["enum"])
    return table


def _prose_not_applicable() -> dict[str, set[str]]:
    """The same table as attributes.md states it: each section's '`NotApplicable` for `k`, `k`'."""
    table: dict[str, set[str]] = {k: set() for k in KINDS}
    sections = re.split(r"^## ", ATTRIBUTES_MD, flags=re.MULTILINE)[1:]
    for section in sections:
        name = section.split("\n", 1)[0].strip()
        m = re.search(r"`NotApplicable`\s+for\s+((?:`[a-z-]+`(?:,\s+)?)+)", section)
        for kind in re.findall(r"`([a-z-]+)`", m.group(1)) if m else []:
            table[kind].add(name)
    return table


def test_applicability_table_agrees_across_data_schema_and_prose() -> None:
    data = {k: set(v) for k, v in APPLICABILITY.items()}
    assert set(data) == KINDS, "every subjectKind needs an entry, even an empty one"
    assert data == _schema_not_applicable(), "schema conditionals drifted from the data file"
    assert data == _prose_not_applicable(), "attributes.md 'Applies to' drifted from the data file"
