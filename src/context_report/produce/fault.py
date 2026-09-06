"""Fault producers: what we can measure about a guard script, and the honest gap where we can't."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from context_report.produce import payloads
from context_report.rows import (
    ERROR,
    NOT_AVAILABLE,
    PASSED,
    RE_DERIVABLE,
    Row,
    input_hash,
    not_measured,
)

MALFORMED_OUTPUT_ATTRIBUTE = "fault.malformedOutput"
CLIENT_DEPENDENT_ATTRIBUTES = ("fault.scriptMissing", "fault.interpreterMissing", "fault.timeout")

#: The malformed-input cases fed to the guard script's stdin, in order.
_MALFORMED_STDIN_CASES = {
    "on_malformed_json": "not json{",
    "on_empty_stdin": "",
    "on_null_tool_input": json.dumps({"tool_input": None}),
}

MALFORMED_OUTPUT_REASONING = (
    "exit 0 on malformed input is how a Claude Code hook fails open; whether that is "
    "acceptable is the consumer's threshold."
)

#: Documented vendor fault behaviour (basis vendor-docs, never measured by this producer), from
#: the "Vendor fault semantics" section of the context-attestation prior-art record.
DOCUMENTED_FAULT_BEHAVIOUR: dict[str, str] = {
    "claude_code": (
        "exit 2 blocks; exit 1 or any other non-zero proceeds with a notice; JSON failing "
        "schema is non-blocking; timeout discards the hook's output and the tool call proceeds. "
        "Hooks run in the current cwd with a fallback chain."
    ),
    "copilot": (
        'preToolUse command hooks are fail-closed on crash ("Denied by preToolUse hook (hook '
        'errored)") but "Timeouts are always fail-open, including for preToolUse and '
        'admin-deployed policy hooks"; HTTP hooks fail open on any network error.'
    ),
    "cursor": "failClosed is a per-script option defaulting to false.",
}


def malformed_cases(control_payload: dict | None) -> dict[str, str]:
    """The stdin cases a malformed-output probe feeds a hook, `control_benign` added if given."""
    cases = dict(_MALFORMED_STDIN_CASES)
    if control_payload is not None:
        cases["control_benign"] = json.dumps(control_payload)
    return cases


def malformed_output_row(  # noqa: PLR0913 -- keyword-only; the probe's whole configuration
    command: str,
    artifact_root: Path,
    *,
    timeout_s: float = 10.0,
    target: str = "claude_code",
    control_payload: dict | None = None,
    binding: tuple[object, ...] = (),
) -> Row:
    """Run the guard against malformed stdin -- measurable without a client.

    `would_allow` is exit 0 AND no deny word on stdout: hook_json adapters carry the decision in
    stdout, not the exit code. A benign well-formed `control_benign` case is run alongside so a
    reader can see whether the hook engaged at all; under `bare_allow: silent` protocols a silent
    exit 0 there is expected and is not itself evidence of an early exit.
    """
    artifact_root = Path(artifact_root)
    values: dict[str, dict[str, object]] = {}
    cases = malformed_cases(control_payload)
    for case, stdin_text in cases.items():
        try:
            proc = subprocess.run(  # noqa: S602  # nosemgrep -- run as the client runs it
                command,
                shell=True,
                input=stdin_text,
                capture_output=True,
                timeout=timeout_s,
                cwd=artifact_root,
                text=True,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return not_measured(
                MALFORMED_OUTPUT_ATTRIBUTE,
                ERROR,
                f"case {case!r} raised {exc!r}",
                inputs=(command, list(cases.values()), target),
                binding=binding,
            )
        stderr = proc.stderr or ""
        stdout = proc.stdout or ""
        decision = payloads.stdout_decision(target, stdout)
        values[case] = {
            "exit": proc.returncode,
            "stdout_decision": decision,
            "would_allow": proc.returncode == 0 and not payloads.is_deny(target, decision),
            "stderr_first_line": stderr.splitlines()[0] if stderr else "",
            "stdout_first_line": stdout.splitlines()[0] if stdout else "",
        }
    return Row(
        attribute=MALFORMED_OUTPUT_ATTRIBUTE,
        basis=RE_DERIVABLE,
        result=PASSED,
        input_hash=input_hash(
            *binding, MALFORMED_OUTPUT_ATTRIBUTE, command, list(cases.values()), target
        ),
        conditions={"cwd": "root", "command": command, "cases": list(cases), "target": target},
        values=values,
        reasoning=MALFORMED_OUTPUT_REASONING,
    )


def client_dependent_rows(target: str, *, binding: tuple[object, ...] = ()) -> list[Row]:
    """The honest NotAvailable rows for the three faults that require driving a real client.

    v0.1 never drives a real agent client, so scriptMissing/interpreterMissing/timeout can only
    report the vendor's documented behaviour as an oracle -- explicitly labeled NOT measured.
    """
    oracle = DOCUMENTED_FAULT_BEHAVIOUR.get(target)
    if oracle is None:
        reasoning = (
            f"observing what the {target} client does when the hook fails requires driving "
            f"that client; the v0.1 producer does not. No documented oracle on file for "
            f"{target!r}."
        )
    else:
        reasoning = (
            f"observing what the {target} client does when the hook fails requires driving "
            f"that client; the v0.1 producer does not. Documented behaviour (basis "
            f"vendor-docs, NOT measured): {oracle}"
        )
    return [
        not_measured(attribute, NOT_AVAILABLE, reasoning, inputs=(target,), binding=binding)
        for attribute in CLIENT_DEPENDENT_ATTRIBUTES
    ]
