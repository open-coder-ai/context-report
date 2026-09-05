# paper/

**Status: draft with dogfood numbers.** `context-report.md` is a complete measurement-paper draft,
abstract through conclusion. Section 5 carries the first run of the reference producer over chock's
88 bundles (`measurements/chock/`, 2026-09-05); §5.2 (a catalog sample) and the live-client side of
§5.3 were not run and say so in place. Every other claim is sourced from the discovery records and
plan under `discovery/` and `plan/` in the parent organization repository, and from this repository's
own schema, worked example, producer and verifier, cited in `references.md`. `tests/test_paper.py`
keeps any `[[placeholder]]` visible (its `PLACEHOLDERS` set is empty as of this revision) and checks
that every citation resolves.

To regenerate the measurements behind Section 5, rebuild chock's bundles with
`chock plugin build --format all` for each policy, write the inventory the script expects, and run:

```
PYTHONPATH=src python3 measurements/dogfood_chock.py --targets chock-targets.json --out measurements/chock --n 20
```

The script writes one statement per (bundle, condition) and `SUMMARY.md`; Section 5 is updated by
hand from that summary, and any new `[[placeholder]]` goes into the `PLACEHOLDERS` set in
`tests/test_paper.py` in the same change.
