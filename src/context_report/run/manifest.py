"""The run manifest: metadata on what to measure, validated before any token is spent."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

MANIFEST_VERSION = "v0.1"
MODE_ISOLATED = "isolated"
MODE_LEAVE_ONE_OUT = "leave-one-out"
_SLUG = re.compile(r"[^A-Za-z0-9._-]+")


class ManifestError(ValueError):
    """The manifest is well-formed JSON but cannot be run as written."""


@dataclass(frozen=True)
class Subject:
    id: str
    path: Path
    kind: str
    workdir: Path | None = None  # where the subject model works; None means the run's own cwd


@dataclass(frozen=True)
class ModelRef:
    provider: str
    id: str
    base_url: str | None = None  # openai-compatible: where the endpoint lives
    api_key_env: str | None = None  # openai-compatible: env var holding the bearer key, if any

    @property
    def slug(self) -> str:
        """A filesystem-safe name for this model, used for output paths."""
        return f"{_SLUG.sub('_', self.provider)}--{_SLUG.sub('_', self.id)}"

    @property
    def qualified(self) -> str:
        return f"{self.provider}/{self.id}"


@dataclass(frozen=True)
class Task:
    id: str
    prompt: str
    subjects: tuple[str, ...]  # resolved: never empty
    rules: tuple[str, ...]  # empty means every rule of the named subjects
    criteria: dict[str, str] = field(default_factory=dict)
    # Populated only when `tasks` was a `claude plugin eval` case directory (see evalcases.py);
    # a JSON tasks file leaves them at their defaults.
    tags: tuple[str, ...] = ()  # case tags that were not of the form `rule:<id>`
    vendor_graders: tuple[dict[str, Any], ...] = ()  # graders v0.1's single-turn runner can't run
    regex_graders: tuple[dict[str, Any], ...] = ()  # specs for evalcases.checkers_for
    runs: int | None = None  # a case's own `runs`; only the vendor runner honours it in v0.1


@dataclass(frozen=True)
class Arms:
    n_per_arm: int
    seed: int = 0
    mode: str = MODE_ISOLATED


@dataclass(frozen=True)
class Target:
    name: str
    client_version: str | None = None


@dataclass(frozen=True)
class Manifest:
    subjects: tuple[Subject, ...]
    target: Target
    models: tuple[ModelRef, ...]
    tasks: tuple[Task, ...]
    arms: Arms
    judge: ModelRef | None
    out: Path
    source: Path

    def subject(self, subject_id: str) -> Subject:
        for s in self.subjects:
            if s.id == subject_id:
                return s
        raise KeyError(subject_id)

    def tasks_for(self, subject_id: str) -> tuple[Task, ...]:
        return tuple(t for t in self.tasks if subject_id in t.subjects)


def schema() -> dict[str, Any]:
    blob = files("context_report.data").joinpath("run-v0.1.schema.json").read_text("utf-8")
    return json.loads(blob)


def validate(doc: dict[str, Any]) -> list[str]:
    """Schema errors as `path: message` strings; empty means well-formed."""
    validator = Draft202012Validator(schema())
    return [
        "/".join(str(p) for p in e.absolute_path) + ": " + e.message
        for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path))
    ]


def _resolve(base: Path, raw: str) -> Path:
    p = Path(raw)
    return (p if p.is_absolute() else base / p).resolve()


def _load_tasks(
    doc: dict[str, Any], base: Path, subjects: tuple[Subject, ...]
) -> list[dict[str, Any]]:
    """Resolve `tasks`: a JSON tasks file, an inline list, or a `claude plugin eval` case dir.

    A directory is the source form a plugin developer already writes; `evalcases.load_dir`
    compiles it into the same dict shape the JSON path produces below, so the loop in `load()`
    that turns these into `Task`s never needs to know which source it came from.
    """
    raw = doc.get("tasks")
    if raw is None:
        return []
    if isinstance(raw, str):
        path = _resolve(base, raw)
        if path.is_dir():
            from context_report.run import evalcases  # deferred: evalcases imports this module

            return evalcases.load_dir(path, subjects)
        if not path.is_file():
            raise ManifestError(f"tasks file not found: {path}")
        loaded = json.loads(path.read_text(encoding="utf-8"))
        full = schema()
        task_file_schema = {**full["$defs"]["taskFile"], "$defs": full["$defs"]}
        errors = [e.message for e in Draft202012Validator(task_file_schema).iter_errors(loaded)]
        if errors:
            raise ManifestError(f"{path}: " + "; ".join(errors))
        return list(loaded["tasks"])
    return list(raw["tasks"])


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


OPENAI_COMPATIBLE = "openai-compatible"


def _model_ref(raw: dict[str, Any]) -> ModelRef:
    """One `{provider, id, baseUrl?, apiKeyEnv?}`; an openai-compatible entry must say where."""
    ref = ModelRef(raw["provider"], raw["id"], raw.get("baseUrl"), raw.get("apiKeyEnv"))
    if ref.provider == OPENAI_COMPATIBLE and not ref.base_url:
        raise ManifestError(
            f"model {ref.qualified!r}: provider {OPENAI_COMPATIBLE!r} needs a baseUrl "
            "(the server's API root, e.g. https://api.openai.com/v1)"
        )
    return ref


def _subject(base: Path, raw: dict[str, Any]) -> Subject:
    """One `subjects[]` entry, paths resolved against the manifest and checked to exist."""
    p = _resolve(base, raw["path"])
    if not p.exists():
        raise ManifestError(f"subject path not found: {p}")
    workdir = _resolve(base, raw["workdir"]) if raw.get("workdir") else None
    if workdir is not None and not workdir.is_dir():
        raise ManifestError(f"subject workdir is not a directory: {workdir}")
    return Subject(id=raw.get("id") or p.name, path=p, kind=raw["kind"], workdir=workdir)


def load(path: str | Path) -> Manifest:
    """Read, validate and resolve a manifest; every error is raised before anything runs."""
    source = Path(path).resolve()
    doc = json.loads(source.read_text(encoding="utf-8"))
    errors = validate(doc)
    if errors:
        raise ManifestError(f"{source}: " + "; ".join(errors))
    base = source.parent

    subjects = [_subject(base, raw) for raw in doc["subjects"]]
    ids = [s.id for s in subjects]
    if len(set(ids)) != len(ids):
        raise ManifestError(f"subject ids must be unique: {ids}")

    out = _resolve(base, doc["out"])
    for s in subjects:
        if _inside(out, s.path) or _inside(s.path, out):
            raise ManifestError(f"out {out} overlaps subject {s.id!r}: it would change its digest")

    tasks: list[Task] = []
    for raw in _load_tasks(doc, base, tuple(subjects)):
        named = tuple(raw.get("subjects") or ids)
        unknown = sorted(set(named) - set(ids))
        if unknown:
            raise ManifestError(f"task {raw['id']!r} names unknown subject(s) {unknown}")
        tasks.append(
            Task(
                id=raw["id"],
                prompt=raw["prompt"],
                subjects=named,
                rules=tuple(raw.get("rules") or ()),
                criteria=dict(raw.get("criteria") or {}),
                tags=tuple(raw.get("tags") or ()),
                vendor_graders=tuple(raw.get("vendor_graders") or ()),
                regex_graders=tuple(raw.get("regex_graders") or ()),
                runs=raw.get("runs"),
            )
        )
    task_ids = [t.id for t in tasks]
    if len(set(task_ids)) != len(task_ids):
        raise ManifestError(f"task ids must be unique: {task_ids}")

    arms_raw = doc["arms"]
    judge_raw = doc.get("judge")
    target_raw = doc["target"]
    return Manifest(
        subjects=tuple(subjects),
        target=Target(target_raw["name"], target_raw.get("clientVersion")),
        models=tuple(_model_ref(m) for m in doc["models"]),
        tasks=tuple(tasks),
        arms=Arms(
            n_per_arm=arms_raw["nPerArm"],
            seed=arms_raw.get("seed", 0),
            mode=arms_raw.get("mode", MODE_ISOLATED),
        ),
        judge=_model_ref(judge_raw) if judge_raw else None,
        out=out,
        source=source,
    )
