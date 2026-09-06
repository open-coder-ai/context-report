"""context-report: an open report format for whether an agent context artifact actually works.

Public API for library consumers (a catalog verifying a submitted statement, a CI job producing
one): everything in `__all__`. Anything else in this package is an implementation detail.
"""

from __future__ import annotations

# Set before the submodule imports below: produce.run reads context_report.__version__ at
# import time (it stamps producer.version), so this name must exist first or those imports
# circle back into a not-yet-initialized module.
__version__ = "0.1.0"

from context_report.produce.run import produce_statement
from context_report.run.compare import render_history, render_table
from context_report.run.layout import history_markdown, resolve_run_dir, rule_history_markdown
from context_report.run.manifest import load as load_manifest
from context_report.run.runner import run
from context_report.statement import validate
from context_report.verify import verify_statement as verify

__all__ = [
    "__version__",
    "history_markdown",
    "load_manifest",
    "produce_statement",
    "render_history",
    "render_table",
    "resolve_run_dir",
    "rule_history_markdown",
    "run",
    "validate",
    "verify",
]
