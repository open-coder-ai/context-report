# paper/

**Status: draft with dogfood numbers.** `context-report.md` is a complete measurement-paper draft,
abstract through conclusion. Section 5 carries the first run of the reference producer over chock's
88 bundles (2026-09-05; statements in `open-coder-ai/chock-catalog`, under `measurements/context-report/`); §5.2 (a catalog sample) and the live-client side of
§5.3 were not run and say so in place. Every other claim is sourced from the discovery records and
plan under `discovery/` and `plan/` in the parent organization repository, and from this repository's
own schema, worked example, producer and verifier, cited in `references.md`. `tests/test_paper.py`
keeps any `[[placeholder]]` visible (its `PLACEHOLDERS` set is empty as of this revision) and checks
that every citation resolves.

The measurements behind Section 5 are not in this repository. They live with the artifacts they
measure, in `open-coder-ai/chock-catalog`, under `measurements/context-report/`, with the script and inventory that regenerate them;
that directory's README says how. Section 5 is updated by hand from its `SUMMARY.md`, and any new
`[[placeholder]]` goes into the `PLACEHOLDERS` set in `tests/test_paper.py` in the same change.
