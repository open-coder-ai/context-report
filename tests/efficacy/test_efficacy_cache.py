"""Caching dedupes identical calls, persists across runs, and never returns a wrong answer."""

from context_report.efficacy.cache import CachingJudge, CachingRunner, FileStore, MemStore, key_for


class CountingRunner:
    def __init__(self):
        self.calls = 0

    def run(self, task, rule):
        self.calls += 1
        return f"out::{task}::{rule}"


class CountingJudge:
    def __init__(self, verdict=True):
        self.calls = 0
        self.verdict = verdict

    def obeys(self, rule, task, output, criterion):
        self.calls += 1
        return self.verdict


def test_runner_dedupes_identical_calls():
    inner = CountingRunner()
    r = CachingRunner(inner, MemStore())
    a = r.run("task", "rule")
    b = r.run("task", "rule")
    assert a == b and inner.calls == 1
    assert r.hits == 1 and r.misses == 1


def test_runner_distinguishes_arms_and_tasks():
    inner = CountingRunner()
    r = CachingRunner(inner, MemStore())
    r.run("t", "rule")
    r.run("t", None)
    r.run("t2", "rule")
    assert inner.calls == 3


def test_judge_caches_bool_verdict():
    inner = CountingJudge(verdict=False)
    j = CachingJudge(inner, MemStore())
    assert j.obeys("r", "t", "out", "c") is False
    assert j.obeys("r", "t", "out", "c") is False
    assert inner.calls == 1 and j.hits == 1


def test_judge_does_not_serve_one_criterion_verdict_to_another():
    """Same rule, task and output; different question. A shared key would answer the wrong one."""
    inner = CountingJudge(verdict=False)
    j = CachingJudge(inner, MemStore())
    j.obeys("r", "t", "out", "refuses outright")
    j.obeys("r", "t", "out", "refuses and names an alternative")
    assert inner.calls == 2 and j.hits == 0


def test_model_label_prevents_cross_model_collision():
    store = MemStore()
    a = CachingRunner(CountingRunner(), store, model="haiku")
    b = CachingRunner(CountingRunner(), store, model="opus")
    a.run("t", "r")
    b.run("t", "r")
    assert a.misses == 1 and b.misses == 1


def test_file_store_persists_across_instances(tmp_path):
    path = tmp_path / "cache.json"
    inner1 = CountingRunner()
    CachingRunner(inner1, FileStore(path)).run("t", "r")
    inner2 = CountingRunner()
    r2 = CachingRunner(inner2, FileStore(path))
    r2.run("t", "r")
    assert inner2.calls == 0 and r2.hits == 1


def test_corrupt_cache_file_is_a_cold_cache(tmp_path):
    path = tmp_path / "cache.json"
    path.write_text("not json{", encoding="utf-8")
    inner = CountingRunner()
    CachingRunner(inner, FileStore(path)).run("t", "r")
    assert inner.calls == 1


def test_key_is_stable_and_order_sensitive():
    assert key_for("a", "b") == key_for("a", "b")
    assert key_for("a", "b") != key_for("b", "a")
