# context-report

[![CI](https://github.com/open-coder-ai/context-report/actions/workflows/ci.yml/badge.svg)](https://github.com/open-coder-ai/context-report/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/open-coder-ai/context-report/badge)](https://scorecard.dev/viewer/?uri=github.com/open-coder-ai/context-report)

An open, signed report format for one question: **does this agent context artifact actually work?**

A plugin, an `AGENTS.md`, a skill, a hook, an MCP server. Every catalog ships them; nothing proves
they behave as declared, cost what they cost, or fail the way their author thinks they do.

`context-report` is an [in-toto](https://github.com/in-toto/attestation) predicate an author produces
in their own CI and a catalog verifies at submission. It states measured facts, **per target agent**,
and never says "pass" or "fail" for the artifact as a whole — the consumer sets thresholds.

## Install

```
pip install -e ".[dev]"
```

Not yet published to PyPI — install from a checkout of this repository. The optional
`context-report[efficacy]` extra pulls in the `anthropic` client for the `efficacy` row;
see [Verify](#verify) below.

## The one idea that makes self-certification honest

Every row carries a `basis`:

| `basis` | Meaning | How a verifier treats it |
| :--- | :--- | :--- |
| `re-derivable` | deterministic; recomputable from the subject plus the recorded configuration | a **cache** it may recompute; a mismatch is a rejected submission |
| `claimed` | stochastic or author-reported (e.g. efficacy by ablation) | a **labeled claim**, bound to model and date, never proof |

A `re-derivable` row must carry an `inputHash` over its exact inputs. That hash is what makes the
word checkable rather than asserted.

## Status

**v0.1 draft.** The schema, one worked example and its tests are here. The reference producer and
verifier are not yet. Per in-toto convention, `0.X` versions are major: fields may change until 1.0.

- Schema: [`spec/attestation/v0.1/schema.json`](spec/attestation/v0.1/schema.json)
- Example: [`spec/attestation/v0.1/examples/plugin-copilot.json`](spec/attestation/v0.1/examples/plugin-copilot.json)
- Predicate type: `https://open-coder-ai.github.io/context-report/attestation/v0.1`
- Hosted: https://open-coder-ai.github.io/context-report/attestation/v0.1/ (schema.json alongside)

## Rows in v0.1

`conformance` · `reachability` · `decision` · `fault.scriptMissing` · `fault.interpreterMissing` ·
`fault.timeout` · `fault.malformedOutput` · `cost.latency_ms` · `cost.context_tokens` ·
`interference` · `efficacy`. Extensions use an `x-` prefix. A row that could not be measured says
`NotAvailable`, `Error` or `NotApplicable` **and why** — an unmeasured row is never a pass.

## Borrowed, deliberately

Field names come from formats that already settled them: in-toto Statement/v1 and Test Result,
SCAI's attribute assertions, SLSA Provenance's `producer`/`metadata`/`byproducts`, CycloneDX's
`confidenceInterval` and `reasoning`, Criterion's `estimate`, JMH's percentile map, Glama TDQS's
`inputHash`, OpenSSF Scorecard's `NotApplicable` outcomes. Only `basis` is new.

## Verify

```
pip install -e ".[dev]"
python -m pytest -q
python -m ruff check .
```

Efficacy — paired-ablation measurement of whether an artifact changes agent behaviour — ships as
the optional extra `context-report[efficacy]` (`pip install -e ".[efficacy]"`) and is the engine
behind the `efficacy` row: `context-report efficacy --help`.

## Running a manifest

`context-report run MANIFEST` measures a whole batch of artifacts, models and tasks in one shot,
from a JSON manifest matching [`spec/run/v0.1/schema.json`](spec/run/v0.1/schema.json):

```
context-report run run.json --dry-run   # rules found/exercised and the call budget, no model touched
context-report run run.json             # the real thing
context-report run run.json --n 2       # override arms.nPerArm for a smoke run
context-report run run.json --resume    # after an interrupted run: reuse every statement and
                                        # matching transcript under `out`, call only for the rest
```

See [`spec/run/v0.1/examples/run.json`](spec/run/v0.1/examples/run.json) and its `tasks.json` for
a worked manifest: two subjects, two models, three tasks.

A subject may set `workdir`, the checkout the subject model works in for that subject's tasks, so
"add this dependency" is answered against the real `package.json`; `claude-cli` models only.

v0.1 supports `arms.mode: "isolated"` only; `"leave-one-out"` is rejected before anything runs.
Two providers have a backend: `anthropic` (the API, needs `ANTHROPIC_API_KEY`) and `claude-cli`
(the local `claude` CLI with its own login; `id` is an alias such as `opus`, `sonnet`, `fable` or a
full model id, so one manifest can compare models). Any other subject model gets a `NotAvailable`
efficacy row explaining there is no backend for it in v0.1, with no arms run and no transcripts
recorded. A `judge` model, if set, must use one of the same two providers; without one, rules with a prose
compliance criterion are reported ungraded rather than guessed at.

The command writes a fixed layout under the manifest's `out` directory:

```
out/manifest.json                                   # the manifest as resolved and run
out/<subject id>/<model slug>.json                  # one statement per subject and model
out/<subject id>/<model slug>/transcripts/           # that pair's recorded model outputs
out/<subject id>/statement.json                      # only when `models` is empty
out/SUMMARY.md                                       # one row per (subject, model)
```

Every `<subject id>/<model slug>.json` is a full context-report statement — schema-valid on its
own — with an `efficacy` row carrying the measured lift (or, for an unsupported provider or an
ungraded rule, an honest explanation of what wasn't measured and why) plus which of the subject's
rules no task exercised. The transcripts directory is what the statement's `byproducts` entry is
bound to by digest, so a re-judge or an audit has the exact recorded outputs to work from.

## Contributing

Bug reports, spec feedback, and PRs are welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md) for the development loop and the DCO sign-off every
commit needs.

## Security

See [SECURITY.md](SECURITY.md) to report a vulnerability privately.

## License

Apache-2.0.
