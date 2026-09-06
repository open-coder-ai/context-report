"""Backend tests — mock the `claude` subprocess so no live model call happens in CI."""

from unittest import mock

import pytest

from context_report.efficacy import cli_backend
from context_report.efficacy.backends import AskerJudge, AskerRunner, parse_yesno
from context_report.efficacy.cli_backend import CliAsker


@pytest.mark.parametrize(
    "text,expected",
    [
        ("YES", True),
        ("NO", False),
        ("yes.", True),
        ("no, it violates", False),
        ("Answer: YES", True),
        ("The output is fine. yes", True),
    ],
)
def test_parse_yesno(text, expected):
    assert parse_yesno(text) is expected


def test_parse_yesno_rejects_garbage():
    with pytest.raises(ValueError):
        parse_yesno("maybe, unclear")


def _fake_run(stdout, returncode=0, stderr=""):
    return mock.Mock(stdout=stdout, returncode=returncode, stderr=stderr)


def _patched(stdout, returncode=0, stderr=""):
    return (
        mock.patch.object(cli_backend.shutil, "which", return_value="/usr/bin/claude"),
        mock.patch.object(
            cli_backend.subprocess, "run", return_value=_fake_run(stdout, returncode, stderr)
        ),
    )


def test_runner_control_arm_omits_the_rule():
    which, run = _patched("out")
    with which, run as m:
        AskerRunner(CliAsker()).run("do X", None)
        prompt = m.call_args.args[0][2]
        assert "do X" in prompt
        assert "Follow this rule" not in prompt


def test_runner_treatment_arm_includes_the_rule():
    which, run = _patched("out")
    with which, run as m:
        AskerRunner(CliAsker()).run("do X", "always use tabs")
        prompt = m.call_args.args[0][2]
        assert "always use tabs" in prompt
        assert "do X" in prompt


def test_judge_maps_yes_no():
    which, run = _patched("YES")
    with which, run:
        assert AskerJudge(CliAsker()).obeys("rule", "task", "output", "crit") is True
    which, run = _patched("NO")
    with which, run:
        assert AskerJudge(CliAsker()).obeys("rule", "task", "output", "crit") is False


def test_nonzero_exit_raises():
    which, run = _patched("", 1, "boom")
    with which, run, pytest.raises(RuntimeError):
        AskerRunner(CliAsker()).run("t", None)


def test_missing_cli_raises():
    with (
        mock.patch.object(cli_backend.shutil, "which", return_value=None),
        pytest.raises(RuntimeError),
    ):
        CliAsker().ask("anything")
