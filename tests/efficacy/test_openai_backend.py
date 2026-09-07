"""The openai-compatible backend against a local server: request shape, auth, usage, errors."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import ClassVar
from unittest import mock

import pytest

from context_report.efficacy import openai_backend
from context_report.efficacy.openai_backend import OpenAICompatibleAsker

SEEN: list[dict] = []


class _Handler(BaseHTTPRequestHandler):
    status: ClassVar[int] = 200
    body: ClassVar[dict] = {}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        SEEN.append(
            {
                "path": self.path,
                "auth": self.headers.get("Authorization"),
                "json": json.loads(self.rfile.read(length)),
            }
        )
        payload = json.dumps(_Handler.body).encode("utf-8")
        self.send_response(_Handler.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args):  # silence the test output
        return


@pytest.fixture
def server():
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    SEEN.clear()
    yield f"http://127.0.0.1:{httpd.server_port}/v1"
    httpd.shutdown()


def test_asks_the_chat_completions_endpoint_with_a_bearer_key(server, monkeypatch):
    monkeypatch.setenv("TEST_KEY", "sk-test")
    _Handler.status = 200
    _Handler.body = {
        "model": "llama-served",
        "choices": [{"message": {"role": "assistant", "content": "  fine  "}}],
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 7,
            "prompt_tokens_details": {"cached_tokens": 100},
        },
    }
    asker = OpenAICompatibleAsker("llama", server, api_key_env="TEST_KEY")
    assert asker.ask("hello") == "fine"
    assert SEEN[0]["path"] == "/v1/chat/completions"
    assert SEEN[0]["auth"] == "Bearer sk-test"
    assert SEEN[0]["json"] == {"model": "llama", "messages": [{"role": "user", "content": "hello"}]}
    assert asker.last_usage == {
        "inputTokens": 120,
        "outputTokens": 7,
        "uncachedInputTokens": 20,
        "cacheReadInputTokens": 100,
    }
    assert asker.last_model == "llama-served"


def test_a_local_server_needs_no_key_and_a_named_key_must_be_set(server, monkeypatch):
    _Handler.status = 200
    _Handler.body = {"choices": [{"message": {"content": "ok"}}]}
    assert OpenAICompatibleAsker("m", server).ask("x") == "ok"
    assert SEEN[0]["auth"] is None
    monkeypatch.delenv("MISSING_KEY", raising=False)
    with pytest.raises(RuntimeError, match="MISSING_KEY"):
        OpenAICompatibleAsker("m", server, api_key_env="MISSING_KEY").ask("x")


def test_http_errors_and_odd_answers_are_plain_errors(server):
    _Handler.status = 429
    _Handler.body = {"error": "slow down"}
    with pytest.raises(RuntimeError, match="429"):
        OpenAICompatibleAsker("m", server).ask("x")
    _Handler.status = 200
    _Handler.body = {"choices": []}
    with pytest.raises(RuntimeError, match="choices"):
        OpenAICompatibleAsker("m", server).ask("x")


def test_base_url_must_be_http_and_one_timeout_is_retried():
    with pytest.raises(ValueError, match="http"):
        OpenAICompatibleAsker("m", "ftp://nope")
    asker = OpenAICompatibleAsker("m", "http://localhost:1/v1", timeout=1)
    good = mock.MagicMock()
    good.read.return_value = json.dumps({"choices": [{"message": {"content": "late"}}]}).encode()
    good.__enter__.return_value = good
    with mock.patch.object(
        openai_backend.urllib.request, "urlopen", side_effect=[TimeoutError(), good]
    ) as m:
        assert asker.ask("x") == "late"
        assert m.call_count == 2
    with (
        mock.patch.object(
            openai_backend.urllib.request, "urlopen", side_effect=[TimeoutError(), TimeoutError()]
        ),
        pytest.raises(RuntimeError, match="no answer within 1s"),
    ):
        asker.ask("x")
