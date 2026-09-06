# paper/

**Status: draft with dogfood and catalog-sample numbers.** `context-report.md` is a complete
measurement-paper draft, abstract through conclusion, cut to figures-plus-tables so a reader can
take it in without wading through prose. Section 5 carries the first run of the reference producer
over chock's 88 bundles and a sample of 18 public Claude Code plugins (statements held for
`open-coder-ai/chock-catalog` PR #57 until the format is public); the live-client side of §5.3 was
not run and says so in place. Every other claim is sourced from the discovery records and plan
under `discovery/` and `plan/` in the parent organization repository, and from this repository's
own schema, worked example, producer and verifier, cited in `references.md`. `tests/test_paper.py`
keeps any `[[placeholder]]` visible (its `PLACEHOLDERS` set is empty as of this revision) and checks
that every citation resolves.

The measurements behind Section 5 are not in this repository. They live with the artifacts they
measure: `open-coder-ai/chock-catalog` PR #57 holds them, with the script and inventory that
regenerate them, until this format is public, and they are regenerated before they land there;
that directory's README says how. Section 5 is updated by hand from its `SUMMARY.md`, and any new
`[[placeholder]]` goes into the `PLACEHOLDERS` set in `tests/test_paper.py` in the same change.

## Figures

`figures/*.svg` are regenerated, not hand-drawn (except `fig-pipeline.svg` and
`fig-two-models.svg`, which are hand-authored SVG embedded in the same script as fixed strings):

```bash
python paper/figures/make_figures.py [--chock-statements PATH]
```

Without `--chock-statements`, the chock dogfood numbers come from `figures/data/chock_dogfood.json`
— a copy of the paper's own §5.1 table, sourced once from the statements the flag would otherwise
read live from `open-coder-ai/chock-catalog`'s held checkout. Output is deterministic
(`svg.hashsalt` plus stripped `Date`/`Creator` metadata): the same statements produce the same
bytes every run, which is what `tests/test_figures.py` checks. Regenerate after any change to the
catalog-sample statements under `measurements/catalog-sample/` or to the chock fallback data, and
commit the new SVGs alongside.

## Word-count budget

A maintenance rule, not a one-time target: `context-report.md` stays at or under 4,000 words and
`measurements/catalog-sample/SUMMARY.md` at or under 700, both measured by `wc -w`. A change that
adds prose to either file re-checks the count and cuts elsewhere (or moves the content into a
table or figure) before landing — the whole point of the cut this repository went through was that
a reader takes these in from figures and short text, and letting either file creep back past its
budget undoes that.
