"""Backend that calls the Claude API directly: reproducible runs, needs a credential."""

from __future__ import annotations

DEFAULT_MODEL = "claude-opus-5"
JUDGE_EFFORT = "low"
_MAX_TOKENS = 16000
_SDK_MISSING = (
    "the `anthropic` package is required for the api backend: "
    "pip install 'context-report[efficacy]'"
)


class ApiAsker:
    """Ask the Claude API one prompt; ``effort='low'`` suits the judge."""

    def __init__(self, model: str = DEFAULT_MODEL, effort: str | None = None) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError(_SDK_MISSING) from exc
        self.client = anthropic.Anthropic()
        self.model = model
        self.effort = effort

    def ask(self, prompt: str) -> str:
        params = {
            "model": self.model,
            "max_tokens": _MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.effort is not None:
            params["output_config"] = {"effort": self.effort}
        response = self.client.messages.create(**params)
        return "".join(block.text for block in response.content if block.type == "text").strip()
