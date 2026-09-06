# context-report measurements of real-world instructions and skills

Research data for the paper: rules and instructions from real repositories, measured with the
reference `context-report` producer (Layer 1, every subject, deterministic) and the `run`
efficacy engine (Layer 2, three subjects, three subject models) — each a real third-party
artifact measured at a pinned commit, never authored, modified, or influenced by this repository
or its maintainers. No author of any measured file was contacted; nothing here is a request, a
report, or a claim sent to them.

`SUMMARY.md` is the source list and commits, the selection choices, the Layer 1 table, the two
`compare` tables, and what the rows say. `inventory.json` is the Layer 1 machine-readable index
(source, url, path, commit, kind, digest, statement file, rules extracted, skipped by reason).
`extract_stats.py` recomputes those extraction counts from the cloned sources.
`<source>/<name>.json` are the Layer 1 statements themselves. `efficacy/` holds the Layer 2
manifest (`run.json`), the hand-written eval cases (`evals/`), and the run's full output
(`out/`: `manifest.json`, one statement per subject and model, transcripts, `SUMMARY.md`) copied
in so the paper's efficacy numbers are re-derivable from committed data.

Every re-derivable Layer 1 row (`cost.context_tokens`) should recompute identically against a
fresh clone at the recorded commit. The measured source repositories are not part of this commit —
they were cloned read-only into a scratch directory to run the producer and the manifest against,
and nothing under them was modified.
