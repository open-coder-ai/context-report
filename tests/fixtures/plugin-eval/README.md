# Constructed fixture

`aggregate-result.json` in this directory is hand-constructed from the early-access field list in
Claude Code's `claude plugin eval --ablation with-without` reference (no public schema exists yet
to capture a real run against): it is not output captured from an actual vendor run. It carries two
cases — one tagged `rule:never-commit-secrets` with a clear positive lift, one untagged (so its
pseudo rule id is its own case name) with zero lift — plus a grader `type` outside the reference's
known enum and `tokens` present on some runs and absent on others, to exercise `pluginval.py`'s
tolerance for the fields the reference leaves optional. Replace this file with a captured one from
a real `claude plugin eval` run once one is available, and delete this notice when it is.
