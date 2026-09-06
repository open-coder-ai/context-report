# run manifest v0.1

Manifest schema:

```
https://open-coder-ai.github.io/context-report/run/v0.1/schema.json
```

- [schema.json](schema.json) — the JSON Schema for `context-report run`'s input
- [examples/run.json](examples/run.json) — a worked example
- [examples/evals/](examples/evals/) — hand-written `claude plugin eval` cases; the worked
  `run.json` points `tasks` at this directory
- [examples/tasks.json](examples/tasks.json) — a standalone example of the compiled JSON task
  form `evals/` above compiles down to
- [README.md](README.md) — field-by-field guide to the manifest, including "Tasks as eval cases"

Running a manifest produces `context-report` statements under the
[attestation/v0.1](../../attestation/v0.1/) predicate:

```
https://open-coder-ai.github.io/context-report/attestation/v0.1
```

## Versioning

Per in-toto convention, `0.X` versions are major: fields may change until 1.0. Consumers **MUST**
ignore unknown fields.
