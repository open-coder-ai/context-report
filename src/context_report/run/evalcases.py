"""Compile a `claude plugin eval` case directory into the task dicts `manifest.load` consumes.

Layout (see `spec/run/v0.1/README.md#tasks-as-eval-cases` for the full mapping):

    <tasks-dir>/<case-name>/prompt.md          # frontmatter + prompt body -> one Task
    <tasks-dir>/<case-name>/graders/*.md       # frontmatter `type` + fields; body may hold a rubric
    <tasks-dir>/<case-name>/case.yaml          # optional; ignored in v0.1
    <tasks-dir>/mocks/<server>/<tool>.md       # optional; ignored in v0.1

The JSON tasks file stays the compiled form this module produces; nobody hand-writes it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from context_report.efficacy.core import RuleCard
from context_report.efficacy.fastjudge import Checker, GraderRegex
from context_report.run.manifest import ManifestError, Subject, Task

_IGNORED_TOP_LEVEL = {"mocks"}
_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?(.*)\Z", re.DOTALL)
_RULE_TAG = re.compile(r"^rule:(.+)$")
_LLM_TYPE = "llm"
_REGEX_TYPE = "regex"
_LAST_MESSAGE = "last_message"
# Grader types the single-turn v0.1 runner has no data to check (no tool trace, no filesystem
# diff, no baseline run, no multi-turn ordering); recorded as Task.vendor_graders instead.
_VENDOR_ONLY_TYPES = {"tool_used", "tool_order", "file_exists", "baseline"}


def _frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    """The YAML block between the first two `---` lines, and the trimmed body after it."""
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    if not match:
        raise ManifestError(f"{path}: missing '---' frontmatter block")
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        raise ManifestError(f"{path}: malformed frontmatter: {exc}") from exc
    if meta is None:
        meta = {}
    if not isinstance(meta, dict):
        raise ManifestError(f"{path}: frontmatter must be a YAML mapping")
    return meta, match.group(2).strip()


def _split_tags(tags: list[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """`rule:<id>` tags become rule ids; every other tag is kept verbatim on `Task.tags`."""
    rule_ids, other = [], []
    for tag in tags:
        m = _RULE_TAG.match(tag)
        (rule_ids if m else other).append(m.group(1) if m else tag)
    return tuple(rule_ids), tuple(other)


def _resolve_subjects(
    prompt_path: Path, plugins: list[str], subjects: tuple[Subject, ...]
) -> tuple[str, ...]:
    """`plugins` paths (relative to the case dir) matched to manifest subjects by resolved path.

    No `plugins` means every subject, same default a JSON task uses for an absent `subjects`.
    """
    if not plugins:
        return ()
    by_path = {s.path: s.id for s in subjects}
    ids: list[str] = []
    for raw in plugins:
        resolved = (prompt_path.parent / raw).resolve()
        if resolved not in by_path:
            known = ", ".join(f"{s.id} ({s.path})" for s in subjects) or "(none)"
            raise ManifestError(
                f"{prompt_path}: plugins entry {raw!r} resolves to {resolved}, which matches no "
                f"subject; known subjects: {known}"
            )
        ids.append(by_path[resolved])
    return tuple(ids)


def _bound_rule_ids(grader_meta: dict[str, Any], case_rule_ids: tuple[str, ...]) -> tuple[str, ...]:
    """A grader's own `rule:` field, else the rule ids the case names (possibly none)."""
    single = grader_meta.get("rule")
    if single:
        return (str(single),)
    return case_rule_ids


def _add_criterion(criteria: dict[str, str], rule_ids: tuple[str, ...], text: str) -> None:
    """Bind an `llm` grader's `criteria` text to each rule id, or to `"*"` when none is named.

    `criteria["*"]` is a `context_report.run.evalcases` extension of the `cards_for` contract:
    it means "the default criterion for every rule of this task's named subjects that has no
    more specific entry". `cards_for` (src/context_report/run/cards.py) does not read it yet —
    today it only reads `criteria.get(rule.id, rule.text)` — so an eval case with no `rule:`
    tags gets its rule text as the criterion until an orchestrator wires the `"*"` fallback in.
    """
    for rule_id in rule_ids or ("*",):
        criteria[rule_id] = f"{criteria[rule_id]}\n\n{text}" if rule_id in criteria else text


def _load_graders(
    case_dir: Path, case_rule_ids: tuple[str, ...]
) -> tuple[dict[str, str], tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """criteria, regex-checker specs, and vendor-grader records for one case's `graders/*.md`."""
    criteria: dict[str, str] = {}
    regex_specs: list[dict[str, Any]] = []
    vendor: list[dict[str, Any]] = []
    graders_dir = case_dir / "graders"
    if not graders_dir.is_dir():
        return criteria, tuple(regex_specs), tuple(vendor)
    for grader_path in sorted(graders_dir.glob("*.md")):
        meta, _body = _frontmatter(grader_path)
        grader_type = meta.get("type")
        if not grader_type:
            raise ManifestError(f"{grader_path}: grader frontmatter missing 'type'")
        if grader_type == _LLM_TYPE:
            text = meta.get("criteria")
            if not text:
                raise ManifestError(f"{grader_path}: llm grader missing 'criteria'")
            _add_criterion(criteria, _bound_rule_ids(meta, case_rule_ids), str(text))
        elif grader_type == _REGEX_TYPE and meta.get("target", _LAST_MESSAGE) == _LAST_MESSAGE:
            regex_specs.append(
                {
                    "pattern": meta.get("pattern", ""),
                    "flags": meta.get("flags") or "",
                    "match": meta.get("match", "contains"),
                    "rule_ids": _bound_rule_ids(meta, case_rule_ids),
                }
            )
        elif grader_type == _REGEX_TYPE or grader_type in _VENDOR_ONLY_TYPES:
            vendor.append({"grader": grader_path.name, **meta})
        else:
            raise ManifestError(f"{grader_path}: unknown grader type {grader_type!r}")
    return criteria, tuple(regex_specs), tuple(vendor)


def _load_case(case_dir: Path, subjects: tuple[Subject, ...]) -> dict[str, Any]:
    """One case directory -> one compiled task dict, shaped like the JSON tasks file's entries."""
    prompt_path = case_dir / "prompt.md"
    meta, body = _frontmatter(prompt_path)
    if not body:
        raise ManifestError(f"{prompt_path}: prompt body is empty")
    rule_ids, tags = _split_tags(list(meta.get("tags") or []))
    subject_ids = _resolve_subjects(prompt_path, list(meta.get("plugins") or []), subjects)
    criteria, regex_specs, vendor = _load_graders(case_dir, rule_ids)
    return {
        "id": case_dir.name,
        "prompt": body,
        "subjects": subject_ids,
        "rules": rule_ids,
        "criteria": criteria,
        "tags": tags,
        "vendor_graders": vendor,
        "regex_graders": regex_specs,
        "runs": meta.get("runs"),
    }


def load_dir(path: Path, subjects: tuple[Subject, ...]) -> list[dict[str, Any]]:
    """Compile every case directory under `path` (the manifest's `tasks` directory).

    `mocks/` at the top level is the vendor's optional mock-tool layout; skipped, not errored.
    Every other immediate subdirectory must be a case directory (it must hold a `prompt.md`).
    """
    if not path.is_dir():
        raise ManifestError(f"tasks directory not found: {path}")
    cases: list[dict[str, Any]] = []
    for case_dir in sorted(p for p in path.iterdir() if p.is_dir()):
        if case_dir.name in _IGNORED_TOP_LEVEL:
            continue
        if not (case_dir / "prompt.md").is_file():
            raise ManifestError(f"{case_dir}: eval case is missing prompt.md")
        cases.append(_load_case(case_dir, subjects))
    return cases


def checkers_for(
    tasks: tuple[Task, ...], cards: list[RuleCard] | None = None
) -> tuple[Checker, ...]:
    """One `GraderRegex` `Checker` per eval-case `regex` grader recorded on these tasks.

    Wiring these into `context_report.efficacy.grade.grade` is the orchestrator's job (see the
    README section "Tasks as eval cases"): today `measure()` in `efficacy/core.py` calls
    `judge.obeys(rule.text, ...)`, so a `Checker.applies`/`obeys` only ever sees rule *text*.
    `GraderRegex` binds by rule *id* instead, since that is what an eval case's `rule:` tags and
    grader `rule:` fields name — the orchestrator needs to pass rule ids through, not text, for
    these checkers to ever fire.
    """
    text_of = {card.id: card.text for card in cards or ()}
    return tuple(
        GraderRegex(
            spec["pattern"],
            spec["flags"],
            spec["match"],
            tuple(spec["rule_ids"]),
            tuple(text_of[r] for r in spec["rule_ids"] if r in text_of),
        )
        for task in tasks
        for spec in task.regex_graders
    )
