"""Content-hash caching for Runner/Judge — never pay for the same model call twice."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Protocol

from context_report.efficacy.core import Judge, Runner


def key_for(*parts: object) -> str:
    """Stable content hash of the parts (order-sensitive, type-tagged via JSON)."""
    blob = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class Store(Protocol):
    """A key-value store for cached model answers."""

    def get(self, key: str) -> str | None:
        """The cached value, or None."""

    def set(self, key: str, value: str) -> None:
        """Remember `value` under `key`."""


class MemStore:
    def __init__(self) -> None:
        self._d: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._d.get(key)

    def set(self, key: str, value: str) -> None:
        self._d[key] = value


class FileStore:
    """JSON-file cache that persists across runs. Load-once, write-through on set."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._d: dict[str, str] = {}
        if self.path.exists():
            try:
                self._d = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._d = {}

    def get(self, key: str) -> str | None:
        return self._d.get(key)

    def set(self, key: str, value: str) -> None:
        self._d[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._d, sort_keys=True), encoding="utf-8")


class CachingRunner:
    """Wrap a Runner; identical (model, task, rule) calls return the stored output."""

    def __init__(self, inner: Runner, store: Store, model: str = "default") -> None:
        self.inner, self.store, self.model = inner, store, model
        self.hits = self.misses = 0

    def run(self, task: str, rule: str | None) -> str:
        key = key_for("run", self.model, task, rule)
        cached = self.store.get(key)
        if cached is not None:
            self.hits += 1
            return cached
        self.misses += 1
        out = self.inner.run(task, rule)
        self.store.set(key, out)
        return out


class CachingJudge:
    """Wrap a Judge; identical (model, rule, task, output, criterion) judgments return the store.

    The criterion is part of the key, not decoration: the same output judged against a different
    criterion is a different question, and omitting it would serve one case's verdict to another.
    """

    def __init__(self, inner: Judge, store: Store, model: str = "default") -> None:
        self.inner, self.store, self.model = inner, store, model
        self.hits = self.misses = 0

    def obeys(self, rule: str, task: str, output: str, criterion: str) -> bool:
        key = key_for("judge", self.model, rule, task, output, criterion)
        cached = self.store.get(key)
        if cached is not None:
            self.hits += 1
            return cached == "1"
        self.misses += 1
        verdict = self.inner.obeys(rule, task, output, criterion)
        self.store.set(key, "1" if verdict else "0")
        return verdict
