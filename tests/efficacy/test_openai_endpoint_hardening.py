"""The openai-compatible endpoint and key variable are constrained before any request is made."""

from __future__ import annotations

import json
from unittest import mock

import pytest

from context_report.efficacy.openai_backend import OpenAICompatibleAsker

_OK = (200, json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode())


@pytest.mark.parametrize(
    "url",
    ["http://example.com/v1", "http://10.0.0.5:8000/v1", "http://localhost.evil.example/v1"],
)
def test_plain_http_is_refused_unless_the_host_is_loopback(url):
    with pytest.raises(ValueError, match="https"):
        OpenAICompatibleAsker("m", url)


@pytest.mark.parametrize(
    "url", ["http://localhost:11434/v1", "http://127.0.0.1:8000/v1", "http://[::1]:8000/v1"]
)
def test_loopback_http_stays_allowed(url):
    OpenAICompatibleAsker("m", url)


@pytest.mark.parametrize("env", ["GITHUB_TOKEN", "PATH", "aws_secret", "FAKE_TOKEN_VAR", "A B_KEY"])
def test_api_key_env_must_follow_the_key_name_convention(env):
    with pytest.raises(ValueError, match="apiKeyEnv"):
        OpenAICompatibleAsker("m", "https://api.openai.com/v1", api_key_env=env)


@pytest.mark.parametrize("env", ["OPENAI_API_KEY", "MY_PROVIDER_KEY"])
def test_conventional_key_names_are_accepted(env):
    OpenAICompatibleAsker("m", "https://api.openai.com/v1", api_key_env=env)


def test_first_request_to_a_non_default_host_warns_with_the_host(monkeypatch, capsys):
    monkeypatch.setenv("CUSTOM_API_KEY", "sk-test")
    asker = OpenAICompatibleAsker("m", "https://llm.example.net/v1", api_key_env="CUSTOM_API_KEY")
    with mock.patch.object(asker, "_send", return_value=_OK):
        asker.ask("x")
        asker.ask("y")
    err = capsys.readouterr().err
    assert err.count("llm.example.net") == 1  # once, not per request
    assert "sk-test" not in err


def test_default_and_loopback_hosts_do_not_warn(monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    for url in ("https://api.openai.com/v1", "http://localhost:11434/v1"):
        asker = OpenAICompatibleAsker("m", url, api_key_env="OPENAI_API_KEY")
        with mock.patch.object(asker, "_send", return_value=_OK):
            asker.ask("x")
    assert capsys.readouterr().err == ""
