# context-report changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Per in-toto convention, `0.X` versions are major: fields may change until 1.0.

## Unreleased

### Added

- `openai-compatible` provider for `models[]` and `judge`: any server speaking the OpenAI
  chat-completions shape, hosted or local, with `baseUrl` and an optional `apiKeyEnv`; standard
  library only, no SDK.

### Changed

- `statement.validate()` now prefixes every schema error with its JSON-pointer-style path
  (`predicate/attributes/3/environmentSensitive: ...`), matching the convention `run/manifest.py`
  already used; a root-level error gets the stable `(root)` prefix instead of an empty one. A
  `const` mismatch also names the expected and offending values in the same line. The two
  `validate()` functions now share one formatter, `context_report.schema_errors`.

## [0.1.0] - 2026-09-06

First public release: the format, a reference producer and verifier, a run manifest for
paired-ablation measurement, and three measurements in the paper.

### Format

- Attestation predicate v0.1 (`spec/attestation/v0.1/schema.json`): an in-toto Statement whose
  rows carry `basis: re-derivable` (recomputes from the subject, with an `inputHash`) or
  `claimed`; results `PASSED`, `WARNED`, `FAILED`, `NotAvailable`, `Error`, `NotApplicable`; an
  applicability table per subject kind; a worked example.
- Run manifest v0.1 (`spec/run/v0.1/schema.json`): subjects, target agent, models, tasks, arms,
  judge and output directory for one measurement; tasks as JSON or as `claude plugin eval` case
  directories; the rule-id algorithm stated so other tools can name a rule.

### Commands

- `produce`: conformance, reachability (hooks discovered from the plugin itself), the fault rows
  (`scriptMissing`, `interpreterMissing`, `timeout`, `malformedOutput`), `cost.latency_ms` and
  `cost.context_tokens` with subject-relative file names.
- `verify`: schema validity and, with `--subject`, that every re-derivable row recomputes.
- `run`: every subject against every model over the tasks, one statement per pair; every run kept
  under `out/runs/<id>/` with `runs.json` and a side-by-side `SUMMARY.md`; `--resume` continues an
  interrupted run without re-spending recorded calls; `--dry-run` prints the call budget;
  `subjects[].workdir` puts the subject model in the right checkout.
- `judge`: re-grade recorded transcripts with another judge model, writing `.judged.json` siblings.
- `compare`: efficacy by model or subject; `--history` across runs; `--history --rules` per rule.
- `ingest-eval`: an `aggregate-result.json` from `claude plugin eval` as an efficacy row.
- Two model backends: `anthropic` (the API) and `claude-cli` (the local `claude` CLI, so one
  manifest compares `opus`, `sonnet` and `fable` under the account's own login). No model is
  hardcoded; every model comes from the manifest. Input tokens count the cached prefix.

### Library

- `context_report.__all__`: `validate`, `verify`, `produce_statement`, `load_manifest`, `run`,
  `resolve_run_dir`, `history_markdown`, `rule_history_markdown`, `render_table`,
  `render_history`; `py.typed` ships in the wheel. See `docs/library.md`.
- Published to PyPI via trusted publishing on a `v*` tag (`.github/workflows/release.yml`).

### Measurements (in `paper/`)

- chock's 88 plugin bundles across four target agents; 18 public Claude Code plugins; seven
  third-party instruction files and skills, three of them ablated on opus, sonnet and fable with a
  fixed judge. Every statement is committed and re-derives from the recorded commits.

### Known limits

- Fault rows for a live client (`timeout`, crash posture) are `NotAvailable`: v0.1 does not drive
  a client. Efficacy is always a `claimed` row. The tokenizer is an approximation. Coding agents
  only: Claude Code, Codex CLI, GitHub Copilot, Cursor.

[Unreleased]: https://github.com/open-coder-ai/context-report/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/open-coder-ai/context-report/releases/tag/v0.1.0
