<div align="center">

<h1>context-report</h1>

<p><b>Supply-chain trust for agent context.</b><br>
A signed, re-derivable report of whether an agent plugin, hook, skill, <code>AGENTS.md</code> or MCP
server actually works — and how it fails when it doesn't.</p>

[![CI](https://github.com/open-coder-ai/context-report/actions/workflows/ci.yml/badge.svg)](https://github.com/open-coder-ai/context-report/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/context-report)](https://pypi.org/project/context-report/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/open-coder-ai/context-report/badge)](https://scorecard.dev/viewer/?uri=github.com/open-coder-ai/context-report)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
<br>
[![in-toto Statement/v1](https://img.shields.io/badge/in--toto-Statement%2Fv1-D9B45C?labelColor=0D1626)](spec/attestation/v0.1/README.md#envelope)
[![Signed via Sigstore (actions/attest)](https://img.shields.io/badge/signed_via-Sigstore_%28actions%2Fattest%29-D9B45C?labelColor=0D1626)](spec/attestation/v0.1/README.md#envelope)
[![Report rows: 11](https://img.shields.io/badge/report_rows-11-D9B45C?labelColor=0D1626)](#what-a-report-proves)
[![Spec: v0.1 draft](https://img.shields.io/badge/spec-v0.1_draft-D9B45C?labelColor=0D1626)](spec/attestation/v0.1/README.md)

</div>

<p align="center">
  <img src="https://raw.githubusercontent.com/open-coder-ai/context-report/main/docs/assets/demo.gif" width="760" alt="Terminal recording: context-report produce measures my-plugin, a two-file Claude Code plugin bundle (a PreToolUse hook that denies a command containing &quot;destructive-pattern&quot;), for reachability, cost and fault, writing report.json; context-report verify then reprints every row's re-derivable or claimed basis and ends with the line 'well-formed and bound: True'.">
</p>

`context-report` is an open, signed report format for one question: **does this agent context
artifact actually work?**

## Why it matters: a guard you can't see run is not a guard

A plugin, an `AGENTS.md`, a skill, a hook, an MCP server — every catalog ships them, and none come
with evidence attached. You install a "security hook" and trust that it fires. The measurement
behind this repo shows why that trust needs evidence:

| Finding (from the [measurement paper](paper/context-report.md)) | Security reading |
| :--- | :--- |
| **3 of 18** public Claude Code plugins (`carta-cap-table`, `carta-crm`, `carta-investors`) are *reachable but not executable* — a shared dispatch script with no execute bit: `reachability` `FAILED, 0 of 4`, exit 126 | the hook is registered and never runs: a guard that silently isn't there |
| **Every hook that runs**, across both samples, **allows on malformed input** | hooks **fail open** — malformed input goes through instead of being blocked |
| Hooks that shell out to `npx` cost **916.8–941.5 ms p50**; a local script **7.3–53.9 ms**; context weight spans roughly **1,500 to 147,000 tokens** | the cost of a guard varies by two orders of magnitude, per tool call and per context window |
| **No efficacy row reaches `PASSED`**; a prompt-injection rule moved nothing on any model | a rule the agent *reads* is advice, not a control — measure it before relying on it |

Nobody records whether the artifact reaches the agent at all, how it fails when it can't run, or
what it costs in latency and context tokens, and whether the artifact's own instructions change
what the agent does is rarely checked at all. `context-report` is a predicate an author's CI
produces and a catalog verifies at submission — one row per fact, a `basis` declaring whether the
row is recomputable or only claimed, and never a "pass"/"fail" for the artifact as a whole (the
consumer sets its own thresholds).

**Signed like any other supply-chain artifact.** A report is an
[in-toto Statement/v1](https://github.com/in-toto/attestation), bound to the artifact **by
digest**. A producer SHOULD emit it via [`actions/attest`](https://github.com/actions/attest),
which wraps it in a DSSE envelope inside a Sigstore bundle, signs it with the CI workflow's OIDC
identity via Fulcio and records it in the public Rekor log; a consumer checks it with
`gh attestation verify <artifact> --predicate-type https://open-coder-ai.github.io/context-report/attestation/v0.1`.
See [the spec's Envelope section](spec/attestation/v0.1/README.md#envelope).

## 30-second quickstart

```bash
pip install context-report
mkdir -p my-plugin/hooks
cat > my-plugin/hooks/guard.py <<'PY'
#!/usr/bin/env python3
import json, sys
event = json.load(sys.stdin)
command = event.get("tool_input", {}).get("command", "")
if "destructive-pattern" in command:
    print(json.dumps({"decision": "deny", "reason": "blocked destructive command"}))
sys.exit(0)
PY
cat > my-plugin/hooks/hooks.json <<'JSON'
{
  "hooks": {
    "PreToolUse": [
      {"hooks": [{"command": "python3", "args": ["${CLAUDE_PLUGIN_ROOT}/hooks/guard.py"]}]}
    ]
  }
}
JSON
context-report produce --subject ./my-plugin --kind plugin --target claude_code --n 20 --out report.json
context-report verify report.json --subject ./my-plugin
```

`verify` reprints each row's `basis` and `result`, then ends with `well-formed and bound: True` —
never a "pass" for the artifact as a whole. `report.json` is one row per fact; each row's `basis`
is **re-derivable** (anyone can recompute it from the subject) or **claimed** (the author asserts
it). Three real rows from the `report.json` this exact block just produced:

```json
[
  {
    "attribute": "reachability",
    "basis": "re-derivable",
    "result": "FAILED",
    "inputHash": "sha256:fc126ed825ddfeb440a0d1d5bf133780e4b275b8c4c18d1556ea5ab251405bc9",
    "conditions": {"cwdTested": ["root", "nested", "parent", "outside"]},
    "values": {"reachable_from": ["parent"], "unreachable_from": ["root", "nested", "outside"]}
  },
  {
    "attribute": "fault.malformedOutput",
    "basis": "re-derivable",
    "result": "PASSED",
    "inputHash": "sha256:85fab0cf63d9db25ab5aba6ada7d396feceb0474f3018f83c24ce542441c1a88",
    "conditions": {"cases": ["on_malformed_json", "on_empty_stdin", "on_null_tool_input", "control_benign"]},
    "reasoning": "exit 0 on malformed input is how a Claude Code hook fails open; whether that is acceptable is the consumer's threshold."
  },
  {
    "attribute": "cost.context_tokens",
    "basis": "re-derivable",
    "result": "PASSED",
    "inputHash": "sha256:8d2af315178e658732a9e48147395296f8b33277bfb7413d55ad9722053b9026",
    "conditions": {"tokenizer": "approx-regex-v1", "files": 1},
    "measurement": {"unit": "tokens", "n": 1, "min": 50, "max": 50, "mean": 50}
  }
]
```

`reachability` `FAILED` here is not a bug in the example: `${CLAUDE_PLUGIN_ROOT}` resolves to the
relative path `./my-plugin` you passed, so the hook only starts from the one cwd where that path
still points at the plugin — the exact failure mode the measurement below calls out.

The full statement has 11 rows, not 3 — every row's basis, from this exact quickstart block run
fresh:

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/open-coder-ai/context-report/main/docs/figures/fig-row-basis-dark.svg">
  <img alt="Of 11 rows in the report.json this quickstart block produces, 3 are recomputed from the artifact, 1 is the author's unverified claim, and 7 have not been measured this run — shown as absence of evidence, not a weak score." src="https://raw.githubusercontent.com/open-coder-ai/context-report/main/docs/figures/fig-row-basis-light.svg" width="760">
</picture>

Beyond one statement at a time, `context-report run` drives a whole manifest — subjects × models ×
tasks — and `context-report compare` puts every run of that manifest side by side; see
[`docs/cli.md`](docs/cli.md) for the manifest schema, `--dry-run`/`--n`/`--resume`, and which
model providers a manifest can reach.

## What a report proves

Eleven v0.1 rows, each answering one question a security reviewer would otherwise take on faith.
A row that could not be measured says `NotAvailable`, `Error` or `NotApplicable` **and why** —
never a silent pass. Full definitions:
[`spec/attestation/v0.1/attributes.md`](spec/attestation/v0.1/attributes.md).

| Row | Question it answers | Why it matters for security | v0.1 reference producer |
| :--- | :--- | :--- | :--- |
| `reachability` | Is the artifact registered where the agent reads it, from every cwd? | a guard that never starts is a guard you don't have | ✅ measured, re-derivable |
| `fault.malformedOutput` | On malformed input, does the tool call proceed or block? | fail-open vs fail-closed, per hook | ✅ measured, re-derivable |
| `fault.scriptMissing` · `fault.interpreterMissing` · `fault.timeout` | Script gone, interpreter missing, or too slow: does the call proceed? | the ways a guard silently disappears in a fresh environment | ◻ `NotAvailable` (needs a live client); cites a vendor-docs oracle where one is on file |
| `cost.latency_ms` | Wall-clock time added per tool call | what every guarded tool call pays | ✅ measured, re-derivable |
| `cost.context_tokens` | Tokens added to the agent's context window | context weight competes with the task and with other rules | ✅ measured, re-derivable |
| `efficacy` | Does installing it change what the agent does? | whether a rule the agent *reads* does anything at all | ◐ measured by `context-report run` ablation; `claimed` (stochastic) |
| `conformance` | Does it validate against the agent's own bundle/manifest schema? | a malformed bundle can be quietly ignored | ◻ `NotAvailable` in v0.1 |
| `decision` | Does a hook allow/deny exactly as its author declared? | the guard blocks what it says it blocks | ◻ `NotAvailable` — [good first contribution](CONTRIBUTING.md#good-first-contributions) |
| `interference` | Does it shadow or contradict another installed artifact? | one artifact overriding another's guard | ◻ `NotAvailable` — [good first contribution](CONTRIBUTING.md#good-first-contributions) |

Subject kinds (`subjectKind`): `plugin` · `instruction-file` (e.g. `AGENTS.md`) · `skill` ·
`hook` · `mcp-server` · `subagent`.

## What a report looks like

Trimmed from a committed statement over a real public plugin
(`paper/measurements/catalog-sample/official/ai-plugins.json`):

```json
{
  "subjectKind": "plugin",
  "target": {"name": "claude_code"},
  "attributes": [
    {
      "attribute": "cost.context_tokens",
      "basis": "re-derivable",
      "result": "PASSED",
      "inputHash": "sha256:4e85a09a2014600e...",
      "conditions": {"tokenizer": "approx-regex-v1", "files": 2},
      "measurement": {"unit": "tokens", "n": 1, "mean": 2289}
    }
  ]
}
```

v0.1 rows: `conformance` · `reachability` · `decision` · `fault.scriptMissing` ·
`fault.interpreterMissing` · `fault.timeout` · `fault.malformedOutput` · `cost.latency_ms` ·
`cost.context_tokens` · `interference` · `efficacy` (extensions use an `x-` prefix). A row that
could not be measured says `NotAvailable`, `Error` or `NotApplicable` **and why** — never a silent
pass. **v0.1 draft**: schema at
[`spec/attestation/v0.1/schema.json`](spec/attestation/v0.1/schema.json), worked example at
[`spec/attestation/v0.1/examples/plugin-copilot.json`](spec/attestation/v0.1/examples/plugin-copilot.json),
predicate type `https://open-coder-ai.github.io/context-report/attestation/v0.1`, hosted at
https://open-coder-ai.github.io/context-report/attestation/v0.1/.

## Three measurements

The [measurement paper](paper/context-report.md) ran the reference producer over chock's 88
bundles, a sample of 18 public Claude Code plugins, and seven third-party instruction files and
skills. Three findings from that run:

**Reachable is not the same as executable.** Of 18 public plugins, three (`carta-cap-table`,
`carta-crm`, `carta-investors`) share a dispatch script with no execute bit — `reachability`
`FAILED, 0 of 4`, exit 126. Every hook that runs, across both samples, allows on malformed input.
See [§5.2](paper/context-report.md#52-top-n-catalog-plugins).

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/open-coder-ai/context-report/main/docs/figures/fig-catalog-status-dark.svg">
  <img alt="Grid of 18 catalog plugins by 4 measured attributes: three plugins fail reachability outright, every plugin that measures malformed-input handling passes it, and not-applicable cells are shown as a neutral dash, never a low score." src="https://raw.githubusercontent.com/open-coder-ai/context-report/main/docs/figures/fig-catalog-status-light.svg" width="760">
</picture>

**Cost spans two orders of magnitude.** Hooks that shell out to `npx` cost 916.8–941.5 ms p50; a
local script costs 7.3–53.9 ms. Context weight varies about a hundredfold across the sample,
roughly 1,500 to 147,000 tokens. See [§5.2](paper/context-report.md#52-top-n-catalog-plugins).

![Per-hook latency, p50 to p95, log scale](paper/figures/fig-latency.svg)

**No efficacy row reaches `PASSED`.** Three instruction files, ablated on `opus`, `sonnet` and
`fable` (168 recorded transcripts, one judge model held fixed): with four observations per arm the
95% interval is about ±0.49 wide, and the row reports the interval instead of rounding it to a
verdict. A naming-convention rule was the one consistent positive (+0.25 to +0.50 on every model);
a prompt-injection rule moved nothing on any model. See
[§5.3](paper/context-report.md#53-instruction-files-and-skills-three-models).

![Pooled efficacy lift per subject and model](paper/figures/fig-efficacy-lift.svg)

## Who it's for

| Who | What they want |
| :--- | :--- |
| An artifact author | a report their own CI can produce before anyone else asks for one |
| A catalog maintainer | a submission format their existing verifier can check without adopting anyone else's test suite, and a `re-derivable`/`claimed` split to build a policy on |
| A team adopting agent tooling | evidence, per target agent, that a guard starts, how it fails and what it costs, before it runs on the team's machines |
| A researcher or reviewer | a re-derivable record of what was actually measured, not a vendor's prose description of it |

A catalog corroborates a submission by recomputing the `re-derivable` rows itself and diffing
`inputHash` and `result` row by row; any verdict lives in a separate statement (e.g. an in-toto
SVR v0.2 verdict), never inside the report. See [the spec](spec/attestation/v0.1/README.md).

## Two models, not one

Efficacy needs two roles, never one: the **subject model** runs a task with the rule prepended and
without it; the **judge model** never performs the task, only reads the transcript and decides
whether that arm met the rule's criterion, held fixed across every subject model so a comparison
across models is fair. A machine-checkable criterion is graded by code instead, never guessed at.

Subject models come from the manifest, never from code — one manifest lines up every model you can
reach, the API-shaped ones answering without tools or a checkout:

| Provider | What it reaches |
| :--- | :--- |
| `anthropic` | the Anthropic API |
| `claude-cli` | the local `claude` CLI — compares `opus`, `sonnet` and `fable` under one account login |
| `openai-compatible` | any server speaking the chat-completions shape, given a `baseUrl`: hosted (OpenAI, Gemini, Mistral, Groq) or local (Ollama, vLLM, LM Studio) |
| anything else | an honest `NotAvailable` efficacy row, never a guess |

See [`docs/cli.md`](docs/cli.md#every-model-you-can-reach) for the full picture of what a manifest
can reach.

## Use as a library

Beyond the CLI, `context_report` exposes a small stable API for a catalog or CI job to import
directly: `validate`, `verify`, `produce_statement`, `load_manifest`, `run`, `resolve_run_dir`,
`history_markdown`, `rule_history_markdown`, `render_table`, `render_history` (see `__all__` in
[`context_report/__init__.py`](src/context_report/__init__.py)).

```python
from context_report import validate, verify

errors = validate(stmt)  # schema errors, [] means well-formed
result = verify(stmt, subject_path="clone/")  # bound + schema check, never a verdict
```

See [`docs/library.md`](docs/library.md) for a full catalog-verification and CI-production example.

## Supported agents

`produce` drives the subject's own hook command through recorded per-target payloads — no live
agent required. `reachability`, `cost.latency_ms` and `fault.malformedOutput` are re-derivable for
every target below; the three fault rows that need a live client (`fault.scriptMissing`,
`fault.interpreterMissing`, `fault.timeout`) are always `NotAvailable` in v0.1 and cite a vendor-docs
oracle where one is on file (none yet for `codex_cli` — see
[Good first contributions](CONTRIBUTING.md#good-first-contributions)).

| Agent | What is measured | Config file |
| :--- | :--- | :--- |
| `claude_code` | reachability · cost · fault (malformedOutput measured; scriptMissing/interpreterMissing/timeout `NotAvailable`, oracle on file) | `hooks/hooks.json` (+ `.claude-plugin/plugin.json`) |
| `codex_cli` | reachability · cost · fault (malformedOutput measured; scriptMissing/interpreterMissing/timeout `NotAvailable`, no oracle on file) | `hooks/hooks.json` |
| `copilot` | reachability · cost · fault (malformedOutput measured; scriptMissing/interpreterMissing/timeout `NotAvailable`, oracle on file) | `com.github.copilot/hooks/hooks.json` |
| `cursor` | reachability · cost · fault (malformedOutput measured; scriptMissing/interpreterMissing/timeout `NotAvailable`, oracle on file) | `hooks/hooks.json` |

## Part of open-coder-ai

`context-report` is the evidence arm of a family that brings application security to the code AI
agents write: Chock checks that code at the agent's own hook where the client has one, and again
at commit and in CI; `context-report` is the supply-chain evidence for the agent context those
guards ship as — whether a guard actually starts, how it fails and what it costs. *A rule an agent reads is advice. A hook that exits non-zero is a control.*

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/open-coder-ai/context-report/main/docs/figures/family-dark.svg">
  <img alt="The open-coder-ai family: agentseam is the foundation, chock sits on it, chock-catalog feeds chock and generates the four plugin repositories, chock-threat-intel feeds the catalog, and context-report runs as a verification arm measuring all four." src="https://raw.githubusercontent.com/open-coder-ai/context-report/main/docs/figures/family-light.svg" width="800">
</picture>

| Repository | Role |
|---|---|
| [agentseam](https://github.com/open-coder-ai/agentseam) | the primitives — one handler API and a verified capability matrix across 16 agents |
| [chock](https://github.com/open-coder-ai/chock) | the compiler — one policy into git hooks, CI gates and native pre-tool hooks |
| [chock-catalog](https://github.com/open-coder-ai/chock-catalog) | the policies — 48 (19 enforced-at-commit, 9 best-effort in-agent, 20 advisory), 1,179 eval cases, 1,019 replayed deterministically in CI |
| [context-report](https://github.com/open-coder-ai/context-report) | the evidence — a signed report of whether an agent artifact actually works |
| [chock-threat-intel](https://github.com/open-coder-ai/chock-threat-intel) | the threat ledger the catalog's policies answer to — weekly, human-reviewed |
| chock-{claude,cursor,copilot,codex}-plugins | the catalog, packaged for each agent's plugin format (generated) |
| chock-quickstart · chock-example | template repos: what `chock init` leaves behind, and a full adoption |

## Contributing

Bug reports, spec feedback, and PRs are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for the
development loop and the DCO sign-off every commit needs (`git commit -s`). Discussion, spec
proposals, and reports of your own runs happen in
[GitHub Discussions](https://github.com/open-coder-ai/context-report/discussions). See
[SECURITY.md](SECURITY.md) to report a vulnerability privately — for example a `re-derivable` row
that is not actually recomputable, or a verifier accepting a tampered statement.

```bash
python -m ruff check . && python -m ruff format --check . && python -m pytest -q
```

| First contribution | Where it lives |
| :--- | :--- |
| Report your own run — a hook that fails open, a plugin that can't be reached | [Discussions](https://github.com/open-coder-ai/context-report/discussions) |
| Another target agent's payload shape (Windsurf, Zed, Gemini CLI, ...) | `src/context_report/data/payloads-v0.1.json` |
| `codex_cli`'s documented fault behaviour | `src/context_report/produce/fault.py` |
| A producer that drives a live client for the fault rows | `src/context_report/produce/fault.py` |
| `decision` replay · `interference` measurement | `src/context_report/produce/run.py` |
| A real tokenizer behind a new `method` value | `src/context_report/produce/cost.py` |
| `leave-one-out` arms | `src/context_report/run/runner.py` |
| Another instruction-file or skill sample for the paper's measurements | `paper/measurements/instruction-sample/` |

Each is scoped under [Good first contributions](CONTRIBUTING.md#good-first-contributions). Comment
on a [`good first issue`](https://github.com/open-coder-ai/context-report/labels/good%20first%20issue)
to claim it, and keep the `Co-Authored-By` trailer if an agent helped — every diff is read in full
before merge either way.

## License

Apache-2.0.
