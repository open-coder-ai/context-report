"""Recorded arms replay exactly, and the without arm is shared across rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from context_report.efficacy import transcripts as tr
from context_report.efficacy.core import RuleCard, Scenario, measure

CARDS = [
    RuleCard("no-secrets", "Never commit secrets.", (Scenario("t1", "Add the key.", "no key"),)),
    RuleCard("no-force", "Never force-push.", (Scenario("t1", "Add the key.", "no push"),)),
]


class Echo:
    """A runner whose output names its arm, so a replay can be checked against the record."""

    def __init__(self) -> None:
        self.calls = 0
        self.last_usage = {"inputTokens": 3, "outputTokens": 5}

    def run(self, task: str, rule: str | None) -> str:
        self.calls += 1
        return f"{'with' if rule else 'without'}:{self.calls}"


class AlwaysYes:
    def obeys(self, rule: str, task: str, output: str, criterion: str) -> bool:
        return True


def test_recording_runner_writes_one_file_per_arm_and_trial(tmp_path: Path) -> None:
    bundle = tr.Bundle(tmp_path / "b")
    rec = tr.RecordingRunner(Echo(), bundle, subject_id="s", model="anthropic/m", cards=CARDS)
    for card in CARDS:
        measure(card, rec, AlwaysYes(), trials=2)
    names = sorted(p.name for p in bundle.root.glob("*.json"))
    assert names == [
        "t1.-.without.0.json",
        "t1.-.without.1.json",
        "t1.-.without.2.json",
        "t1.-.without.3.json",
        "t1.no-force.with.0.json",
        "t1.no-force.with.1.json",
        "t1.no-secrets.with.0.json",
        "t1.no-secrets.with.1.json",
    ]
    assert rec.tokens == {"inputTokens": 24, "outputTokens": 40}
    assert rec.tokens_per_arm == {
        "with": {"inputTokens": 12, "outputTokens": 20},
        "without": {"inputTokens": 12, "outputTokens": 20},
    }
    first = bundle.read_all()[0]
    assert (
        first.subject_id == "s" and first.model == "anthropic/m" and first.usage["inputTokens"] == 3
    )


def test_replay_serves_recorded_outputs_without_the_model(tmp_path: Path) -> None:
    bundle = tr.Bundle(tmp_path / "b")
    echo = Echo()
    rec = tr.RecordingRunner(echo, bundle, subject_id="s", model="m", cards=CARDS)
    measure(CARDS[0], rec, AlwaysYes(), trials=2)
    recorded = echo.calls

    class Spy:
        def __init__(self) -> None:
            self.seen: list[str] = []

        def obeys(self, rule: str, task: str, output: str, criterion: str) -> bool:
            self.seen.append(output)
            return True

    spy = Spy()
    measure(CARDS[0], tr.ReplayRunner(bundle, CARDS), spy, trials=2)
    assert echo.calls == recorded, "replay must not call the model"
    assert sorted(spy.seen) == sorted(t.output for t in bundle.read_all())


def test_replay_of_an_unrecorded_arm_is_an_error(tmp_path: Path) -> None:
    bundle = tr.Bundle(tmp_path / "b")
    bundle.root.mkdir()
    with pytest.raises(tr.MissingTranscriptError):
        tr.ReplayRunner(bundle, CARDS).run("Add the key.", None)


def test_bundle_descriptor_is_a_resource_descriptor_bound_by_digest(tmp_path: Path) -> None:
    bundle = tr.Bundle(tmp_path / "b")
    tr.RecordingRunner(Echo(), bundle, subject_id="s", model="m", cards=CARDS).run("x", None)
    d = bundle.descriptor("transcripts")
    assert d["name"] == "transcripts" and d["mediaType"] == tr.MEDIA_TYPE
    assert len(d["digest"]["sha256"]) == 64
    (bundle.root / "extra.json").write_text("{}")
    assert bundle.descriptor("transcripts")["digest"] != d["digest"], "digest binds the contents"


def test_resume_reuses_a_matching_transcript_and_records_the_rest(tmp_path: Path) -> None:
    """A resumed recorder serves the transcript already on disk and calls the model for the rest."""
    bundle = tr.Bundle(tmp_path / "b")
    first = Echo()
    tr.RecordingRunner(first, bundle, subject_id="s", model="m", cards=CARDS).run("t1", None)
    assert first.calls == 1

    second = Echo()
    rec = tr.RecordingRunner(second, bundle, subject_id="s", model="m", cards=CARDS, resume=True)
    assert rec.run("t1", None) == bundle.read_all()[0].output  # trial 0: reused, not asked
    rec.run("t1", None)  # trial 1: not on disk, asked
    assert (second.calls, rec.reused) == (1, 1)
    assert rec.tokens["inputTokens"] == 6  # the reused transcript's usage still counts

    other_model = tr.RecordingRunner(
        Echo(), bundle, subject_id="s", model="m2", cards=CARDS, resume=True
    )
    other_model.run("t1", None)
    assert other_model.reused == 0  # another model's transcript is never reused


def test_without_resume_an_existing_transcript_is_overwritten(tmp_path: Path) -> None:
    bundle = tr.Bundle(tmp_path / "b")
    tr.RecordingRunner(Echo(), bundle, subject_id="s", model="m", cards=CARDS).run("t1", None)
    echo = Echo()
    rec = tr.RecordingRunner(echo, bundle, subject_id="s", model="m", cards=CARDS)
    rec.run("t1", None)
    assert (echo.calls, rec.reused) == (1, 0)
