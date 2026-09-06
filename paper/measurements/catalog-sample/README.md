# context-report measurements of third-party catalog plugins

Research data for the paper's §5.2 ("Top-N catalog plugins"): 18 public Claude Code plugins from
the official plugin marketplace and two widely-starred community marketplaces, each a real
third-party artifact measured at a pinned commit with the reference `context-report` producer —
never authored, modified, or influenced by this repository or its maintainers. No author of any
measured plugin was contacted; nothing here is a request, a report, or a claim sent to them.

`SUMMARY.md` is the selection rule, the marketplaces and their commits, the machine, the per-plugin
table, and what the rows say. `inventory.json` is the machine-readable index (marketplace, plugin,
repo, path, commit, subject digest, statement file). `<marketplace>/<plugin>.json` are the
statements themselves, one per plugin, each a complete, schema-valid `context-report` v0.1
statement bound by digest to the plugin directory it measured.

Every re-derivable row (`reachability`, `fault.malformedOutput`, `cost.context_tokens`) should
recompute identically against a fresh clone at the recorded commit; `cost.latency_ms` recomputes as
a comparable distribution, not the same numbers — see `SUMMARY.md`'s "Reproduce" section. A
statement whose subject digest no longer matches a re-clone describes bytes that have since
changed; treat it as describing history, not the plugin's current state.

The measured plugin repositories are not part of this commit — they were cloned read-only into a
scratch directory to run the producer against, and nothing under them was modified.
