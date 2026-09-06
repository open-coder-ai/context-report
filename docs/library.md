# Using context-report as a library

`pip install context-report` gets a catalog or CI job the same functions the CLI wraps:
`context_report.validate`, `verify`, `produce_statement`, `load_manifest`, `run`,
`resolve_run_dir`, `history_markdown`, `rule_history_markdown`, `render_table`, `render_history`. See
`__all__` in
`context_report/__init__.py` for the exact list; nothing else in the package is public API.

## A catalog verifying a submitted statement

A submission is a statement JSON file plus a clone of the artifact it describes. Three checks,
in order: does it conform to the schema, is it bound to *this* clone, and only then read the rows.

```python
import json
from context_report import validate, verify

stmt = json.loads(open("submission.json").read())

errors = validate(stmt)  # schema errors; [] means well-formed
if errors:
    raise SystemExit(f"rejected: {errors}")

result = verify(stmt, subject_path="clone/")  # re-derives the subject digest and compares it
if not result.ok:
    raise SystemExit(
        f"rejected: schema={result.schema_errors} bound={result.subject_digest_matches}"
    )

# result.ok only means "well-formed and bound to this clone" -- never "the artifact is good".
# Each row states a fact; the catalog's own threshold decides pass/fail on it.
rows = stmt["predicate"]["attributes"]
for row in rows:
    if row["attribute"] == "cost.latency_ms" and row["basis"] == "re-derivable":
        p95 = row["measurement"]["percentiles"]["95"]
        if p95 > CATALOG_LATENCY_BUDGET_MS:
            raise SystemExit(f"rejected: p95 latency {p95}ms over budget")
    if row["attribute"] == "conformance" and row["result"] != "PASSED":
        raise SystemExit(f"rejected: conformance {row['result']}")
```

`result.rederivable` and `result.claimed` split row names by `basis`, and `result.unmeasured`
lists rows the producer could not measure — each with a `result` of `NotAvailable`, `Error` or
`NotApplicable` and a reason string, never silently dropped.

## A CI job producing one

An artifact author's CI runs `produce_statement` against the checked-out artifact and writes the
result next to it (or into `steps.upload-artifact`) for the catalog to pick up on submission:

```python
import json
from pathlib import Path
from context_report import produce_statement

stmt = produce_statement(
    subject=Path("."),  # the artifact's own checkout
    subject_kind="plugin",  # one of statement.SUBJECT_KINDS
    target="claude_code",  # the agent this run measured against
    producer_id="https://github.com/acme/my-plugin/.github/workflows/context-report.yml",
)
Path("context-report.json").write_text(json.dumps(stmt, indent=2))
```

`produce_statement` never calls a model; the `efficacy` row it emits is `NotAvailable` unless an
`efficacy_row` computed separately (see `context-report efficacy --help`) is passed in.

## Batch runs and history

`load_manifest("run.json")` plus `run(manifest)` drive the same batch measurement
`context-report run` does from the CLI, writing into `out/runs/<run id>/`. `resolve_run_dir(out)`
finds the latest run; `render_table(out)` and `render_history(out)` (or the lower-level
`history_markdown`, and `rule_history_markdown` for the per-rule view) produce the same tables
`SUMMARY.md` holds, for a script to print or diff.
