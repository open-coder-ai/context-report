# context-report is public: a signed report for whether an agent context artifact actually works

Plugin catalogs, instruction-file repositories, and MCP registries are growing fast, and almost
none of them ask for evidence. The official MCP registry says outright that it "does not certify"
that a listed server's code is secure, its tool descriptions are honest, or its runtime behavior
will stay unchanged. Most plugin marketplaces ask for a schema-valid manifest and "basic automated
review." That is namespace hygiene, not evidence that an artifact reaches the agent, fails safely,
or costs what its author says it costs.

`context-report` is an open format for that evidence. It is an [in-toto](https://github.com/in-toto/attestation)
predicate an artifact's author produces in their own CI and a catalog verifies at submission — a
signed, structured statement, not a document a human fills in by hand. Every row states one
measured fact — `reachability`, a `fault.*` mode, `cost.latency_ms`, `cost.context_tokens`,
`interference`, `efficacy` — and every row carries a `basis`: `re-derivable` (a verifier can
recompute it from the subject and the recorded configuration; a mismatch rejects the submission)
or `claimed` (stochastic or author-reported, bound to a model and a date, never proof). The format
never renders a verdict for the artifact as a whole — a consumer sets its own thresholds over the
rows it cares about.

Efficacy — whether an artifact's own instructions change what an agent does — uses two models, not
one: a subject model runs a task with the rule prepended and without it, and a separate judge model
(never the subject model, held fixed across every subject compared) reads the transcript and grades
whether that arm met the rule's criterion. A machine-checkable criterion is graded by code instead.

We ran the reference producer over three samples and report the numbers as measured, not
smoothed. Across chock's 88 bundles for four target agents, every hook was reachable everywhere
with its plugin-root variable set, and unreachable from three of four agents when it was not — and
every hook, in both samples, allowed on malformed input rather than denying it. Across 18 public
Claude Code plugins, three share a dispatch script with no execute bit: `reachability` reads
`FAILED, 0 of 4`, not a silent pass. Hook latency spans two orders of magnitude in that sample —
7.3 to 53.9 ms for a local script, 916.8 to 941.5 ms for a hook that shells out to `npx` — and
context weight spans roughly a hundredfold, about 1,500 to 147,000 tokens. On seven third-party
instruction files and skills, ablated on three models (168 recorded transcripts), no efficacy row
reached `PASSED`: four observations per arm gives a 95% interval about ±0.49 wide, and the row
reports that interval instead of a rounded verdict. One rule — a naming convention — was the one
consistent positive on all three models; a prompt-injection rule moved nothing on any of them.

What this format does not do: it sets no thresholds, certifies nothing, and never tells a catalog
what to accept. `efficacy` is always a labeled claim, bound to the model and date it ran under, not
proof an artifact works everywhere. The fault rows for what a real client does on a crash or
timeout are `NotAvailable` in v0.1 — it does not yet drive a live client, and says so rather than
guessing from documentation.

**Try it in five minutes**: `pip install -e ".[dev]"` from a checkout, then
`context-report produce --subject ./your-artifact --kind plugin --target claude_code --n 20
--out report.json` produces a statement against your own plugin, hook, or instruction file; `context-report
verify report.json --subject ./your-artifact` checks it against the schema.

**How to help**: measure your own artifact and open the resulting statement as a PR to
`spec/attestation/v0.1/examples/`; add a target agent's payload shape to
`src/context_report/data/payloads-v0.1.json` if your agent isn't one of the four covered today; or
read [`spec/attestation/v0.1/README.md`](../spec/attestation/v0.1/README.md) and tell us where a
field name or a `basis` case doesn't hold up. The repository is
[open-coder-ai/context-report](https://github.com/open-coder-ai/context-report); the measurement
paper is at [`paper/context-report.md`](../paper/context-report.md).

---

**280-character post**

context-report: an open, signed report for whether an agent plugin/skill/hook actually works.
Re-derivable rows a catalog can recompute, claimed rows labeled as claims, never a verdict. Ran it
on 88 bundles + 18 public plugins + 7 instruction files. github.com/open-coder-ai/context-report

**Hacker News / Lobsters submission**

Title: context-report: a signed, re-derivable report for agent plugins, hooks, and instruction files
URL: https://github.com/open-coder-ai/context-report
Text: An in-toto predicate an author's CI produces and a catalog verifies — reachability, cost,
faults, and an efficacy claim, each row labeled recomputable or claimed, never a pass/fail verdict.

**Discord/Slack message**

context-report just went public: a signed report format for whether a plugin, `AGENTS.md`, skill,
or hook actually reaches the agent, what it costs, and whether it changes behavior.
Every row is `re-derivable` (a catalog can recompute it) or `claimed` (labeled, never proof) —
no thresholds, no certification, just facts.
Measured 88 bundles, 18 public plugins, and 7 instruction files so far — three plugins turned out
unreachable (exit 126, no execute bit) and every hook allowed malformed input.
Repo: https://github.com/open-coder-ai/context-report — spec feedback and your own reports welcome.
