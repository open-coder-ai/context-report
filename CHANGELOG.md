# context-report changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Per in-toto convention, `0.X` versions are major: fields may change until 1.0.

## Unreleased

### Added

- A public library API in `context_report.__all__` (`validate`, `verify`,
  `produce_statement`, `load_manifest`, `run`, `resolve_run_dir`,
  `history_markdown`, `render_table`, `render_history`) for a catalog or CI
  job to import directly; see [`docs/library.md`](docs/library.md).
- `py.typed`, shipped in the wheel, so type checkers treat the package as typed.
- `.github/workflows/release.yml` — publishes to PyPI via trusted publishing
  (OIDC) on a `v*` tag push.

## [0.1.0] - 2026-09-06

### Added

- Schema v0.1 for the attestation predicate
  (`spec/attestation/v0.1/schema.json`), plus a worked example
  (`spec/attestation/v0.1/examples/plugin-copilot.json`).
- `context-report produce` — builds a statement from a subject artifact:
  conformance, reachability, hook discovery, fault rows
  (`scriptMissing`, `interpreterMissing`, `timeout`, `malformedOutput`), and
  cost rows (`latency_ms`, `context_tokens`).
- `context-report verify` — checks a statement is schema-valid and, with
  `--subject`, that its `re-derivable` rows recompute against the subject.
- `context-report run` — runs a manifest (`spec/run/v0.1/schema.json`) across
  subjects, models and tasks in one shot, writing one statement per
  (subject, model) pair plus a `SUMMARY.md`.
- `context-report judge` / `context-report compare` — grade a transcript
  against a rule's compliance criterion and compare paired-ablation runs.
- `context-report efficacy` (optional extra `context-report[efficacy]`) —
  paired-ablation measurement of whether an artifact changes agent behaviour;
  the engine behind the `efficacy` row. `provider: "anthropic"` only in v0.1.
- Paper draft (`paper/context-report.md`) laying out the format's motivation
  and borrowed field names.

[Unreleased]: https://github.com/open-coder-ai/context-report/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/open-coder-ai/context-report/releases/tag/v0.1.0
