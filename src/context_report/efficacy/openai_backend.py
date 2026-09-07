"""Backend for any server speaking the OpenAI chat-completions shape: no SDK, standard library only.

OpenAI, Gemini's compatibility endpoint, Mistral, Groq, Ollama, vLLM and LM Studio all serve
`POST <base_url>/chat/completions`, so one backend covers hosted and local models alike.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

_TIMEOUT = 600  # one answer can take minutes; a real hang still ends the run
_ATTEMPTS = 2  # a timed-out call is retried once before the run is given up
_SCHEMES = ("http://", "https://")
_BAD_URL = "baseUrl must start with http:// or https://, not {url!r}"
_NO_KEY = "environment variable {env!r} (apiKeyEnv) is not set"
_HTTP_ERROR = "{url} answered {code}: {body}"
_TIMED_OUT = "{url} gave no answer within {seconds}s, {attempts} attempt(s)"
_NO_CHOICE = "{url} answered without a choices[0].message.content"


class OpenAICompatibleAsker:
    """Ask one prompt of a chat-completions endpoint; records the tokens it reports."""

    def __init__(
        self,
        model: str,
        base_url: str,
        api_key_env: str | None = None,
        timeout: int = _TIMEOUT,
    ) -> None:
        if not base_url.startswith(_SCHEMES):
            raise ValueError(_BAD_URL.format(url=base_url))
        self.model = model
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.api_key_env = api_key_env
        self.timeout = timeout
        self.last_usage: dict[str, int] | None = None
        self.last_model: str | None = None

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key_env:
            key = os.environ.get(self.api_key_env)
            if not key:
                raise RuntimeError(_NO_KEY.format(env=self.api_key_env))
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def ask(self, prompt: str) -> str:
        body = json.dumps(
            {"model": self.model, "messages": [{"role": "user", "content": prompt}]}
        ).encode("utf-8")
        request = urllib.request.Request(
            self.url, data=body, headers=self._headers(), method="POST"
        )
        for attempt in range(1, _ATTEMPTS + 1):
            try:
                response = urllib.request.urlopen(request, timeout=self.timeout)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:200]
                raise RuntimeError(
                    _HTTP_ERROR.format(url=self.url, code=exc.code, body=detail)
                ) from exc
            except TimeoutError as exc:
                if attempt == _ATTEMPTS:
                    raise RuntimeError(
                        _TIMED_OUT.format(url=self.url, seconds=self.timeout, attempts=attempt)
                    ) from exc
                continue
            with response:
                return self._parse(json.loads(response.read().decode("utf-8")))
        raise AssertionError("unreachable")  # pragma: no cover

    def _parse(self, doc: dict) -> str:
        try:
            text = doc["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(_NO_CHOICE.format(url=self.url)) from exc
        usage = doc.get("usage") or {}
        if isinstance(usage, dict) and "prompt_tokens" in usage:
            details = usage.get("prompt_tokens_details") or {}
            cached = int(details.get("cached_tokens", 0) or 0)
            prompt_tokens = int(usage.get("prompt_tokens", 0))
            self.last_usage = {
                "inputTokens": prompt_tokens,  # the endpoint's prompt count already includes cache
                "outputTokens": int(usage.get("completion_tokens", 0)),
                "uncachedInputTokens": prompt_tokens - cached,
                "cacheReadInputTokens": cached,
            }
        if isinstance(doc.get("model"), str):
            self.last_model = doc["model"]
        return str(text or "").strip()
