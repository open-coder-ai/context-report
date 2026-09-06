# context-report

[![CI](https://github.com/open-coder-ai/context-report/actions/workflows/ci.yml/badge.svg)](https://github.com/open-coder-ai/context-report/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/open-coder-ai/context-report/badge)](https://scorecard.dev/viewer/?uri=github.com/open-coder-ai/context-report)

`context-report` is an open, signed report format for one question: **does this agent context
artifact actually work?**

## The problem

A plugin, an `AGENTS.md`, a skill, a hook, an MCP server — every catalog ships them, and none come
with evidence attached. Nobody records whether the artifact reaches the agent at all, how it fails
when it can't run, or what it costs in latency and context tokens, and whether the artifact's own
instructions change what the agent does is rarely checked at all. `context-report` is a predicate an
author's CI produces and a catalog verifies at submission — one row per fact, a `basis` declaring
whether the row is recomputable or only claimed, and never a "pass"/"fail" for the artifact as a
whole (the consumer sets its own thresholds).

## 30-second quickstart

```bash
pip install context-report            # once published; today: pip install -e ".[dev]" from a checkout
context-report produce --subject ./my-plugin --kind plugin --target claude_code --n 20 \
  --out report.json                   # one statement: reachability, cost and fault rows for one target
context-report run run.json           # a whole manifest: subjects x models x tasks in one shot
context-report compare out --history  # every run of that manifest side by side
```

The optional `context-report[efficacy]` extra pulls in the `anthropic` client for the `efficacy`
row (`context-report efficacy --help`). `context-report run` reads a JSON manifest matching
[`spec/run/v0.1/schema.json`](spec/run/v0.1/schema.json) — see
[`spec/run/v0.1/examples/run.json`](spec/run/v0.1/examples/run.json) for a worked one (two
subjects, two models, three tasks) — and supports `--dry-run` (rules and call budget, no model
touched), `--n` (override `arms.nPerArm` for a smoke run), and `--resume` (continue the latest run,
reusing every existing statement and matching transcript, calling only for the rest). Two providers
have a backend: `anthropic` (the API) and `claude-cli` (the local `claude` CLI, so one manifest can
compare `opus`/`sonnet`/`fable`); any other subject model gets an honest `NotAvailable` efficacy
row instead of a guess.

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

![Eighteen plugins by four measured attributes](paper/figures/fig-catalog-status.svg)

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

- **An artifact author** wants a report their own CI can produce before anyone else asks for one.
- **A catalog maintainer** wants a submission format their existing verifier can check without
  adopting anyone else's test suite, and a `re-derivable`/`claimed` split to build a policy on.
- **A researcher or reviewer** wants a re-derivable record of what was actually measured, not a
  vendor's prose description of it.

## Two models, not one

Efficacy needs two roles, never one: the **subject model** runs a task with the rule prepended and
without it; the **judge model** never performs the task, only reads the transcript and decides
whether that arm met the rule's criterion, held fixed across every subject model so a comparison
across models is fair. A machine-checkable criterion is graded by code instead, never guessed at.

## Use as a library

Beyond the CLI, `context_report` exposes a small stable API for a catalog or CI job to import
directly: `validate`, `verify`, `produce_statement`, `load_manifest`, `run`, `resolve_run_dir`,
`history_markdown`, `render_table`, `render_history` (see `__all__` in
[`context_report/__init__.py`](src/context_report/__init__.py)).

```python
from context_report import validate, verify

errors = validate(stmt)  # schema errors, [] means well-formed
result = verify(stmt, subject_path="clone/")  # bound + schema check, never a verdict
```

See [`docs/library.md`](docs/library.md) for a full catalog-verification and CI-production example.

## Contributing

Bug reports, spec feedback, and PRs are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for the
development loop and the DCO sign-off every commit needs. Discussion, spec proposals, and reports
of your own runs happen in
[GitHub Discussions](https://github.com/open-coder-ai/context-report/discussions). See
[SECURITY.md](SECURITY.md) to report a vulnerability privately.

## License

Apache-2.0.
