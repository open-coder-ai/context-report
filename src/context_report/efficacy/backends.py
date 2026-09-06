"""Runner and Judge built on any Asker, so a backend only has to answer a prompt."""

from __future__ import annotations

from typing import Protocol

from context_report.efficacy import prompts

_NO_VERDICT = "could not parse a YES/NO verdict from: {text!r}"


class Asker(Protocol):
    """Send one prompt to a model, get its text back."""

    def ask(self, prompt: str) -> str: ...


def parse_yesno(text: str) -> bool:
    """Read a YES/NO verdict from possibly-chatty model output."""
    lowered = text.strip().lower()
    if lowered.startswith("yes"):
        return True
    if lowered.startswith("no"):
        return False
    for word in lowered.replace(".", " ").replace(",", " ").split():
        if word == "yes":
            return True
        if word == "no":
            return False
    raise ValueError(_NO_VERDICT.format(text=text))


class AskerRunner:
    """Run a coding task. ``rule=None`` is the control arm: the rule is absent, not negated."""

    def __init__(self, asker: Asker) -> None:
        self.asker = asker

    def run(self, task: str, rule: str | None) -> str:
        if rule is None:
            return self.asker.ask(task)
        return self.asker.ask(prompts.render("run_with_rule", rule=rule, task=task))

    @property
    def last_usage(self) -> dict[str, int] | None:
        """Token usage of the last call, when the asker reports it (the API backend does)."""
        return getattr(self.asker, "last_usage", None)


class AskerJudge:
    """LLM-as-judge: did the output obey the rule? A forced YES/NO, parsed deterministically."""

    def __init__(self, asker: Asker) -> None:
        self.asker = asker

    def obeys(self, rule: str, task: str, output: str, criterion: str) -> bool:
        return parse_yesno(
            self.asker.ask(
                prompts.render(
                    "judge", rule=rule, task=task, output=output, criterion=criterion or rule
                )
            )
        )
