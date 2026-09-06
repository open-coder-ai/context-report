# run manifest v0.1

Manifest schema:

```
https://open-coder-ai.github.io/context-report/run/v0.1/schema.json
```

- [schema.json](schema.json) — the JSON Schema for `context-report run`'s input
- [examples/run.json](examples/run.json) — a worked example
- [examples/tasks.json](examples/tasks.json) — the example's task file
- [README.md](README.md) — field-by-field guide to the manifest

Running a manifest produces `context-report` statements under the
[attestation/v0.1](../../attestation/v0.1/) predicate:

```
https://open-coder-ai.github.io/context-report/attestation/v0.1
```

## Versioning

Per in-toto convention, `0.X` versions are major: fields may change until 1.0. Consumers **MUST**
ignore unknown fields.
