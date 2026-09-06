# Top-N catalog plugins, measured by context-report v0.1

The paper's §5.2 sample: 18 public Claude Code plugins, chosen by a rule fixed before looking at
any measurement (see "Selection" below), measured with the reference producer, `n = 20` latency
samples, on 2026-09-06.

**Machine**: Linux-6.18.44-fc-v24-x86_64, Python 3.11.15, 4 CPUs.

**Producer version**: `c285c6e4f41910736829381d7448755cf03a2636`
("produce: args keep shell expansion; dash's missing-file wording counts as unreachable",
`open-coder-ai/context-report#18`, on top of `fd746de2a13b46b6f966114c168221248f43fad5`, "produce:
read manifest-declared hooks files and args; exit 126 is unreachable; no bytecode in the subject").
This is the third run of this sample: the first ran on `context-report` `main` before either fix
(`85cce038…`-era); the second ran on `fd746de` and itself surfaced the gap `c285c6e` closes. Five
plugins' worth of this sample's own findings across the two passes are what these two commits
address — see "What changed across the two producer fixes" below.

## Selection

**Marketplaces** (commit cloned in parentheses):

- **Official** — [`anthropics/claude-plugins-official`](https://github.com/anthropics/claude-plugins-official)
  (`85cce0381e7860082641b59d961a2b8c368b8b79`, 2026-09-04), 291 listed plugins.
- **Community, #1 by stars** — [`wshobson/agents`](https://github.com/wshobson/agents)
  (`a30778f8c4e6b0a87567941b7cca4f534bf642b6`), 39,449 stars, 94 listed plugins.
- **Community, #2 by stars** — [`OthmanAdi/planning-with-files`](https://github.com/OthmanAdi/planning-with-files)
  (`d47a61950e784fc4237ba10ddc1e9e198bd0f275`), 26,648 stars, 1 listed plugin.

Stars were read via the GitHub repository-search API (`mcp__github__search_repositories`,
sorted by stars, query "claude code plugin marketplace") on 2026-09-06.
`anthropics/claude-plugins-community` (3,481 stars) was excluded from the "community" slot because
it is anthropics-owned — the two community picks above are the highest-starred marketplace-shaped
repositories (a `.claude-plugin/marketplace.json`) *not* under the `anthropics` org.

**Rule, fixed before inspection:** from the official marketplace, take every plugin that declares
at least one hook, up to 10; fill to 15 with the highest-starred hook-bearing plugins from the two
community marketplaces; add 5 plugins with no hooks to exercise the `NotApplicable` rows.

**Applying it:** every one of the official marketplace's 291 plugin entries was checked for
`hooks/hooks.json` at its pinned commit (238 external `git-subdir`/`url` entries via
`raw.githubusercontent.com`, the rest by reading the marketplace repo's own `plugins/` and
`external_plugins/` trees directly) — 41 declare it there, plus 6 more whose `.claude-plugin/plugin.json`
points `hooks` at a non-default path, plus 6 local plugins shipped in the marketplace repo itself,
for 53 hook-declaring candidates. Ties were broken alphabetically by plugin name (a rule fixed once
the 53 were counted, not per-plugin). The first 10 alphabetically: `agentforce-adlc`, `ai-plugins`,
`altimate-code`, `aws-core`, `aws-serverless`, `aws-startup-advisor`, `azure`, `carta-cap-table`,
`carta-crm`, `carta-investors`.

The two community marketplaces yielded only **3** hook-declaring plugins between them
(`wshobson/agents`: `review-agent-governance`, `protect-mcp`; `planning-with-files`: itself — its
marketplace lists one plugin) — every other plugin in both repos is skills/agents/commands only.
**Fewer than 15 hook-bearing plugins exist under the rule as stated; the sample below has 13, not
15, and this is that finding, not a shortfall in the search.** The 5 no-hook plugins are the first
5 alphabetically among the official marketplace's remaining (non-hook-bearing) 238 entries:
`42crunch-api-security-testing`, `activecampaign`, `adobe-for-creativity`, `agent-sdk-dev`, `aikido`.

18 plugins total: 13 hook-bearing (10 official + 3 community) + 5 no-hook. Every plugin's subject is
its plugin directory (containing `.claude-plugin/plugin.json`) at the commit `inventory.json`
records; repos were cloned read-only into a scratch directory, never modified, and are not part of
this commit.

## Results

Latency is per PreToolUse-hook invocation with a benign payload, `n = 20`, on the build machine —
`environmentSensitive`, read the shape not the absolute number. "Reach (n/4)" is how many of the
four working directories tested (bundle root, a nested directory, the parent, a directory outside
the tree) the client's plugin-root variable let the hook resolve from. "Allow-any" is
`fault.malformedOutput`'s `wouldAllowAny`: whether any of the four malformed-input cases produced a
stdout decision that would let the tool call through.

| Marketplace | Plugin | Hooks (events) | Reach | Reach (n/4) | Allow-any | Latency p50/p95 ms (or reason) | Context tokens | Interpreter |
| :--- | :--- | :--- | :--- | ---: | :---: | :--- | ---: | :--- |
| official | agentforce-adlc | 2 (PreToolUse, PostToolUse) | PASSED | 4/4 | True | 26.8 / 28.7 | 29,625 | python3 |
| official | ai-plugins | 4 (PreToolUse, PostToolUse×2, UserPromptSubmit) | PASSED | 4/4 | True | 32.0 / 37.4 | 2,289 | bash |
| official | altimate-code | 1 (SessionStart only) | NotApplicable — no hook on PreToolUse | — | — | NotApplicable | 3,940 | — |
| official | aws-core | 2 (PreToolUse×2) | PASSED | 4/4 | True | 45.5 / 51.8 | 57,466 | python3 |
| official | aws-serverless | 1 (PostToolUse only) | NotApplicable — no hook on PreToolUse | — | — | NotApplicable | 20,523 | — |
| official | aws-startup-advisor | 1 (SessionStart only) | NotApplicable — no hook on PreToolUse | — | — | NotApplicable | 43,041 | — |
| official | azure | 1 (PostToolUse only) | NotApplicable — no hook on PreToolUse | — | — | NotApplicable | 74,359 | — |
| official | carta-cap-table | 9 (SessionStart×3, PreToolUse×2, UserPromptSubmit, PostToolUse×2, PostModelSwitch) | FAILED | 0/4 | False | Error: exit 126, not executable | 127,818 | sh (see note) |
| official | carta-crm | 7 (SessionStart×3, PreToolUse×2, UserPromptSubmit, PostModelSwitch) | FAILED | 0/4 | False | Error: exit 126, not executable | 44,588 | sh (see note) |
| official | carta-investors | 8 (SessionStart×3, PreToolUse×2, UserPromptSubmit, PostModelSwitch, PostToolUse) | FAILED | 0/4 | False | Error: exit 126, not executable | 146,663 | sh (see note) |
| wshobson-agents | protect-mcp | 2 (PreToolUse, PostToolUse) | PASSED | 4/4 | True | 665.8 / 686.5 | 1,845 | sh → npx (node) |
| wshobson-agents | review-agent-governance | 2 (PreToolUse, PostToolUse) | PASSED | 4/4 | True | 672.0 / 711.2 | 1,634 | sh → npx (node) |
| othmanadi-planning-with-files | planning-with-files | 6 (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PreCompact, Stop) | PASSED | 4/4 | True | 6.0 / 6.2 | 25,179 | sh |
| official | 42crunch-api-security-testing | 0 | NotApplicable — declares no hooks | — | — | NotApplicable | 17,912 | — |
| official | activecampaign | 0 | NotApplicable — declares no hooks | — | — | NotApplicable | 9,069 | — |
| official | adobe-for-creativity | 0 | NotApplicable — declares no hooks | — | — | NotApplicable | 43,647 | — |
| official | agent-sdk-dev | 0 | NotApplicable — declares no hooks | — | — | NotApplicable | NotApplicable (no text files) | — |
| official | aikido | 0 | NotApplicable — declares no hooks | — | — | NotApplicable | 1,509 | — |

## What changed across the two producer fixes

Three passes of this sample exist; only the rows above, from the third pass on `c285c6e`, are
committed here. A reader of the paper should not use numbers from either earlier pass.

- **`aws-core`** (pass 1 → pass 2, `fd746de`): `NotApplicable — the plugin declares no hooks` →
  fully measured. It declares two `PreToolUse` hooks through `.claude-plugin/plugin.json`'s `hooks`
  field (`./com.anthropic.claude-code/hooks/hooks.json`), which discovery started reading in
  `fd746de`. Reachable 4/4, `wouldAllowAny: True`, p50/p95 45.5/51.8 ms; unaffected by `c285c6e`.
- **`azure`** (pass 1 → pass 2, `fd746de`): also `NotApplicable — the plugin declares no hooks` →
  still `NotApplicable`, but now for the true reason. Its `hooks` field (`./hooks/claude-hooks.json`)
  is read from `fd746de` on, but its one hook is on `PostToolUse`, not `PreToolUse`, so it was never
  going to be measured in v0.1 — the row is now reasoned "declares hooks, but none on claude_code's
  pre-tool event" rather than the misleading "declares no hooks." This is what the plugin actually
  declares, not a regression in either fix.
- **`carta-cap-table`, `carta-crm`, `carta-investors`** (pass 1 → pass 2, `fd746de`):
  `reachability: PASSED (4/4)` → `FAILED (0/4)`. Their shared `hooks/dispatch.sh` has no execute bit
  and never ran (caught only by `fault.malformedOutput`/`cost.latency_ms`, both exit 126). Exit 126
  now counts as unreachable — the row a reader would actually want, since the earlier "reachable"
  was true only of the path resolving, not of anything running. Unaffected by `c285c6e`.
- **`agentforce-adlc`** (pass 1 → pass 2, `fd746de`): previously needed two `produce` attempts (the
  first failed outright — the hook's own `__pycache__` write moved the subject digest mid-run).
  Hooks now run under `PYTHONDONTWRITEBYTECODE=1`; the third pass, like the second, produced a
  statement on the first attempt.
- **`planning-with-files`** (pass 2 → pass 3, `c285c6e`): pass 2 read `reachability: PASSED (4/4)`,
  `wouldAllowAny: False`, `cost.latency_ms: Error` — every number spurious, because `fd746de`'s
  `shlex.quote()` single-quoted the hook's `${CLAUDE_PLUGIN_ROOT}/hooks/claude-hook.sh` argument,
  so the shell never expanded it and the script never opened; `dash`'s resulting "cannot open"
  wording didn't match any recognized not-found fragment, so reachability read PASSED for a hook
  that never ran. `c285c6e` quotes only arguments that need it and expands `reachability.py`'s
  fragment list to cover dash — the hook now genuinely opens and runs: `reachability: PASSED (4/4)`
  is now the same result but for the real reason, `wouldAllowAny: True`, and
  `cost.latency_ms: PASSED` at 6.0/6.2 ms p50/p95, the fastest hook in the sample.

All statements affected by either fix have been fully regenerated on `c285c6e`; the versions
committed here are the only ones in this repository.

## What the rows say

**`npx` is a two-order-of-magnitude latency cost.** `protect-mcp` and `review-agent-governance`
(both `wshobson/agents`) invoke `npx protect-mcp@0.7.4 …` from their `PreToolUse` hook: p50 665.8 ms
and 672.0 ms, against 6.0–51.8 ms p50 for the four plugins that shell out to a local
`python3`/`bash`/`sh` script directly (`agentforce-adlc`, `ai-plugins`, `aws-core`,
`planning-with-files`). Unaffected by either producer fix, since neither touches timing.

**Every hook that actually runs exits with something other than a silent allow on malformed
input.** Of the six plugins whose `PreToolUse` hook ran and was timed (`agentforce-adlc`,
`ai-plugins`, `aws-core`, `planning-with-files`, `protect-mcp`, `review-agent-governance`),
`wouldAllowAny` is `True` for all six — this sample's full working-hook set, now that
`planning-with-files` genuinely runs. The three `carta-*` plugins are the only ones left reading
`wouldAllowAny: False`, and for the reason above (missing exec bit): their hooks never start, so
there is nothing to allow or deny.

**Reachable is still not the same claim as executable.** `carta-cap-table`, `carta-crm`, and
`carta-investors` share one dispatch shim, `hooks/dispatch.sh`, committed with git mode `100644`
(no execute bit) in all three plugin directories. `reachability: FAILED (0/4)` now reflects that
directly (exit 126 counts as unreachable since `fd746de`); `fault.malformedOutput`'s
`wouldAllowAny: False` and `cost.latency_ms`'s `Error: exit 126, not executable` agree. No open gap
remains for these three under either fix.

**Context weight is unaffected by either fix.** It is computed from the plugin's skill/manifest text
files, not from running any hook, so `cost.context_tokens` has not moved for any of the 18 plugins
across all three passes. The smallest bundle in the sample (`review-agent-governance`, 1,634 tokens
under `approx-regex-v1`) and the largest (`carta-cap-table`, 127,818) are both hook-bearing; the
no-hook plugins range from 1,509 (`aikido`) to 74,359 (`azure`) tokens. `agent-sdk-dev` has no skill
or hooks text at all — `cost.context_tokens` reports `NotApplicable: no text files to count`, not
zero.

**Nothing still looks surprising or unaddressed in this sample.** Every plugin's rows now match
what its own manifest and files declare: `NotApplicable` where the hook is on the wrong event or
absent, `FAILED`/`Error` where the shipped file cannot execute, and a real measurement everywhere
else. This sample raised several distinct producer gaps across its first two passes (the
`plugin.json`-declared hooks path, `args` being dropped and then over-quoted, exit 126 reading as
reachable, and a hook's own bytecode write mutating its subject); all of them are now closed for
every plugin in this sample. That does not mean discovery is complete in general — only that
nothing in these particular 18 plugins currently exposes a further gap.

No plugin in this sample is named here as broken, misconfigured, or unsafe: every `Error` and
`NotApplicable` row above states what v0.1 measured and why it stopped there, per the reasoning the
statement itself carries. Whether any of these facts crosses a catalog's own bar is the catalog's
threshold to set, not this report's.

## Reproduce

```bash
pip install -e /path/to/context-report          # base install, no [efficacy] extra needed; at c285c6e or later
git clone https://github.com/<owner>/<repo> <dest> && git -C <dest> checkout <commit>   # per inventory.json
context-report produce --subject <plugin dir> --kind plugin --target claude_code --n 20 \
  --out paper/measurements/catalog-sample/<marketplace>/<plugin>.json
context-report verify paper/measurements/catalog-sample/<marketplace>/<plugin>.json --subject <plugin dir>
```

`inventory.json` lists, per plugin, the marketplace, repo URL, path inside the repo, commit, and
subject digest recorded in its statement; re-cloning at that commit and re-running `produce` on a
producer at or after `c285c6e` should reproduce every re-derivable row (`reachability`,
`fault.malformedOutput`, `cost.context_tokens`) exactly and `cost.latency_ms` as a comparable
distribution. Running against an earlier producer reproduces one of the two misreported earlier
passes described above, not these rows.
