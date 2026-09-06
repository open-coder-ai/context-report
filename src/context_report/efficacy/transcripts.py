"""Stored arms: every model output written once, so judging is a separate, repeatable step."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from context_report.efficacy.core import RuleCard, Runner
from context_report.statement import digest_path, now_utc

ARM_WITH = "with"
ARM_WITHOUT = "without"
CONTROL_RULE = "-"  # the without arm does not depend on the rule, so it is shared across rules
MEDIA_TYPE = "application/vnd.context-report.transcripts+json"
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


class MissingTranscriptError(LookupError):
    """A replay asked for an arm the bundle never recorded."""


def input_sha256(task: str, rule: str | None) -> str:
    blob = json.dumps([task, rule], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Transcript:
    """One model output: which subject, model, task, rule and arm produced it, and what it cost."""

    subject_id: str
    model: str
    task_id: str
    rule_id: str
    arm: str
    trial: int
    input_sha256: str
    output: str
    usage: dict[str, int] | None
    recorded_on: str


def _safe(part: str) -> str:
    return _SAFE.sub("_", part)


class Bundle:
    """A directory of transcripts for one (subject, model); its digest goes in `byproducts`."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def path_for(self, t: Transcript) -> Path:
        name = f"{_safe(t.task_id)}.{_safe(t.rule_id)}.{t.arm}.{t.trial}.json"
        return self.root / name

    def write(self, t: Transcript) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.path_for(t)
        path.write_text(json.dumps(asdict(t), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def read_all(self) -> list[Transcript]:
        out = []
        for p in sorted(self.root.glob("*.json")):
            out.append(Transcript(**json.loads(p.read_text(encoding="utf-8"))))
        return out

    def digest(self) -> str:
        return digest_path(self.root)

    def descriptor(self, name: str) -> dict[str, Any]:
        """The in-toto ResourceDescriptor a statement lists under `byproducts`."""
        return {"name": name, "digest": {"sha256": self.digest()}, "mediaType": MEDIA_TYPE}


def _index(cards: list[RuleCard]) -> tuple[dict[str, str], dict[str, str]]:
    """(task text -> task id, rule text -> rule id) from the cards the engine will measure."""
    tasks: dict[str, str] = {}
    rules: dict[str, str] = {}
    for card in cards:
        rules.setdefault(card.text, card.id)
        for s in card.scenarios:
            tasks.setdefault(s.task, s.id)
    return tasks, rules


class RecordingRunner:
    """Run the inner Runner and write every output to the bundle; the without arm is shared."""

    def __init__(
        self, inner: Runner, bundle: Bundle, *, subject_id: str, model: str, cards: list[RuleCard]
    ) -> None:
        self.inner = inner
        self.bundle = bundle
        self.subject_id = subject_id
        self.model = model
        self._tasks, self._rules = _index(cards)
        self._trials: dict[tuple[str, str, str], int] = {}
        self.tokens: dict[str, int] = {"inputTokens": 0, "outputTokens": 0}
        self.tokens_per_arm: dict[str, dict[str, int]] = {
            ARM_WITH: {"inputTokens": 0, "outputTokens": 0},
            ARM_WITHOUT: {"inputTokens": 0, "outputTokens": 0},
        }

    def run(self, task: str, rule: str | None) -> str:
        output = self.inner.run(task, rule)
        usage = getattr(self.inner, "last_usage", None)
        arm = ARM_WITHOUT if rule is None else ARM_WITH
        if usage:
            for k in self.tokens:
                self.tokens[k] += int(usage.get(k, 0))
                self.tokens_per_arm[arm][k] += int(usage.get(k, 0))
        task_id = self._tasks.get(task, _safe(task)[:40])
        rule_id = CONTROL_RULE if rule is None else self._rules.get(rule, _safe(rule)[:40])
        key = (task_id, rule_id, arm)
        trial = self._trials.get(key, 0)
        self._trials[key] = trial + 1
        self.bundle.write(
            Transcript(
                subject_id=self.subject_id,
                model=self.model,
                task_id=task_id,
                rule_id=rule_id,
                arm=arm,
                trial=trial,
                input_sha256=input_sha256(task, rule),
                output=output,
                usage=dict(usage) if usage else None,
                recorded_on=now_utc(),
            )
        )
        return output


class ReplayRunner:
    """Serve stored outputs in trial order, so `measure()` can be re-judged without a model."""

    def __init__(self, bundle: Bundle, cards: list[RuleCard]) -> None:
        self._tasks, self._rules = _index(cards)
        self._queues: dict[tuple[str, str, str], list[str]] = {}
        for t in sorted(bundle.read_all(), key=lambda t: t.trial):
            self._queues.setdefault((t.task_id, t.rule_id, t.arm), []).append(t.output)
        self._cursor: dict[tuple[str, str, str], int] = {}

    def run(self, task: str, rule: str | None) -> str:
        task_id = self._tasks.get(task, _safe(task)[:40])
        rule_id = CONTROL_RULE if rule is None else self._rules.get(rule, _safe(rule)[:40])
        key = (task_id, rule_id, ARM_WITHOUT if rule is None else ARM_WITH)
        outputs = self._queues.get(key)
        if not outputs:
            raise MissingTranscriptError(f"no transcript for {key}")
        i = self._cursor.get(key, 0)
        self._cursor[key] = i + 1
        return outputs[i % len(outputs)]
