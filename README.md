# context-report

An open, signed report format for one question: **does this agent context artifact actually work?**

A plugin, an `AGENTS.md`, a skill, a hook, an MCP server. Every catalog ships them; nothing proves
they behave as declared, cost what they cost, or fail the way their author thinks they do.

`context-report` is an [in-toto](https://github.com/in-toto/attestation) predicate an author produces
in their own CI and a catalog verifies at submission. It states measured facts, **per target agent**,
and never says "pass" or "fail" for the artifact as a whole — the consumer sets thresholds.

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
```

See [`spec/run/v0.1/examples/run.json`](spec/run/v0.1/examples/run.json) and its `tasks.json` for
a worked manifest: two subjects, two models, three tasks.

v0.1 supports `arms.mode: "isolated"` only; `"leave-one-out"` is rejected before anything runs.
Only `provider: "anthropic"` models have a backend — any other subject model gets a `NotAvailable`
efficacy row explaining there is no backend for it in v0.1, with no arms run and no transcripts
recorded. A `judge` model, if set, must also be `anthropic`; without one, rules with a prose
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

## License

Apache-2.0.
