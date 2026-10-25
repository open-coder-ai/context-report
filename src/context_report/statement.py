"""Assemble rows into an in-toto Statement/v1, bind it to an artifact digest, validate it."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from context_report.rows import PREDICATE_TYPE, STATEMENT_TYPE, Row
from context_report.schema_errors import format_errors

SUBJECT_KINDS = ("plugin", "instruction-file", "skill", "hook", "mcp-server", "subagent")


@dataclass(frozen=True)
class Target:
    """The agent the statement is about."""

    name: str
    client_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name}
        if self.client_version:
            d["annotations"] = {"clientVersion": self.client_version}
        return d


@dataclass(frozen=True)
class Producer:
    """Who ran the checks; the analogue of SLSA's builder.id."""

    id: str
    version: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"id": self.id}
        if self.version:
            d["version"] = dict(self.version)
        return d


def _refuse_links_leaving(root: Path) -> None:
    """Refuse a tree holding a link that resolves outside it.

    A linked directory is not walked by the digest but is read through by the producers, and a
    linked file is hashed by its target: either way a row could come from bytes the digest does
    not cover. Links that stay inside the tree point at bytes the digest already counts.
    """
    base = root.resolve()
    for entry in root.rglob("*"):
        if ".git" in entry.parts or not entry.is_symlink():
            continue
        if not entry.resolve().is_relative_to(base):
            rel = entry.relative_to(root).as_posix()
            raise ValueError(
                f"{rel} is a link to a path outside {root.name!r}; the digest would not cover "
                "what it points at. Replace it with the files themselves"
            )


def digest_path(path: str | Path) -> str:
    """sha256 of a file; for a directory, sha256 over sorted `relpath\\0sha256(content)\\n` lines.

    A tree digest defined this simply can be recomputed by anyone with a shell, which is the point.
    """
    p = Path(path)
    if p.is_file():
        return hashlib.sha256(p.read_bytes()).hexdigest()
    if not p.is_dir():
        raise FileNotFoundError(path)
    _refuse_links_leaving(p)
    lines = []
    for f in sorted(x for x in p.rglob("*") if x.is_file() and ".git" not in x.parts):
        lines.append(
            f"{f.relative_to(p).as_posix()}\0{hashlib.sha256(f.read_bytes()).hexdigest()}\n"
        )
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def statement(  # noqa: PLR0913 -- keyword-only; the predicate's fields are the API
    *,
    subject_name: str,
    subject_sha256: str,
    subject_kind: str,
    target: Target,
    producer: Producer,
    rows: list[Row],
    subject_uri: str | None = None,
    started_on: str | None = None,
    finished_on: str | None = None,
    invocation_id: str | None = None,
    configuration: list[dict[str, Any]] | None = None,
    resolved_dependencies: list[dict[str, Any]] | None = None,
    byproducts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One statement per (subject digest, target agent)."""
    if subject_kind not in SUBJECT_KINDS:
        raise ValueError(f"subjectKind must be one of {SUBJECT_KINDS}, not {subject_kind!r}")
    if not rows:
        raise ValueError("a statement needs at least one row")
    subject: dict[str, Any] = {"name": subject_name, "digest": {"sha256": subject_sha256}}
    if subject_uri:
        subject["uri"] = subject_uri
    predicate: dict[str, Any] = {
        "subjectKind": subject_kind,
        "target": target.to_dict(),
        "producer": producer.to_dict(),
        "attributes": [r.to_dict() for r in rows],
    }
    metadata = {
        k: v
        for k, v in {
            "invocationId": invocation_id,
            "startedOn": started_on,
            "finishedOn": finished_on,
        }.items()
        if v
    }
    if metadata:
        predicate["metadata"] = metadata
    if configuration:
        predicate["configuration"] = configuration
    if resolved_dependencies:
        predicate["resolvedDependencies"] = resolved_dependencies
    if byproducts:
        predicate["byproducts"] = byproducts
    return {
        "_type": STATEMENT_TYPE,
        "subject": [subject],
        "predicateType": PREDICATE_TYPE,
        "predicate": predicate,
    }


def schema() -> dict[str, Any]:
    """The v0.1 schema shipped inside the package (kept byte-identical to spec/ by a test)."""
    blob = files("context_report.data").joinpath("attestation-v0.1.schema.json").read_text("utf-8")
    return json.loads(blob)


def validate(stmt: dict[str, Any]) -> list[str]:
    """Schema errors for a statement as `path: message` strings, empty when it conforms.

    Never raises on a bad instance. See `schema_errors.format_error` for the path convention,
    including the `(root)` marker used for a top-level error.
    """
    return format_errors(Draft202012Validator(schema()).iter_errors(stmt))
