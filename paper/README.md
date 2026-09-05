# paper/

**Status: skeleton, numbers pending.** `context-report.md` is a complete measurement-paper draft —
abstract through conclusion — with every claim that depends on a measurement not yet run written as
a `[[placeholder]]` instead of a number. Every other claim is sourced from the discovery records and
plan under `discovery/` and `plan/` in the parent organization repository, and from this repository's
own schema, worked example, and README, cited in `references.md`. Nothing here should be read as a
result; `tests/test_paper.py` enforces that every placeholder stays visible (listed in its
`PLACEHOLDERS` set) so landing a number is a deliberate edit, not something that can be forgotten
silently.

Sections map to the workers who will fill them in once the reference producer and verifier exist.
Section 5, Results, is the only section with no prose to preserve — its three sub-sections
(dogfood on chock's own bundles, a top-N catalog sample, and the fault oracle versus documentation)
are headers and empty-shaped tables, to be replaced wholesale from `measurements/` once the producer
runs. Section 4, Method, describes a plan inferred from the schema and the project plan rather than
a running tool; every methodological detail this draft could not read directly from a source is
marked `[[confirm with W3/W4]]` rather than stated as settled, and those workers own resolving it
before the method section can be called final. Sections 1–3 and 6–8 (introduction, background, the
format, threats to validity, discussion, conclusion) depend only on the source records already
committed and should need no further input beyond copyediting once the numbers land, since none of
their claims cite a number this project has not yet measured.

To regenerate the Results tables once `measurements/` exists, the intended command is:

```
python -m context_report.report --measurements ../measurements/ --out paper/context-report.md --section results
```

This command does not exist yet — there is no `context_report.report` module in this repository as
of this draft — and is recorded here as the shape the regeneration step is expected to take, not as
something that currently runs. Until it exists, update Section 5 by hand from whatever
`measurements/` produces, and keep the `PLACEHOLDERS` set in `tests/test_paper.py` in sync with
whichever placeholders remain in the surrounding prose.
