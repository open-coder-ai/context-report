# Top-N catalog plugins, measured by context-report v0.1

The paper's §5.2 sample: 18 public Claude Code plugins, chosen by a rule fixed before looking at
any measurement (see "Selection" below), measured with the reference producer, `n = 20` latency
samples, on 2026-09-06.

**Machine**: Linux-6.18.44-fc-v24-x86_64, Python 3.11.15, 4 CPUs.

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
points `hooks` at a non-default path the producer does not read (see "What the rows say"), plus 6
local plugins shipped in the marketplace repo itself, for 53 hook-declaring candidates. Ties were
broken alphabetically by plugin name (a rule fixed once the 53 were counted, not per-plugin). The
first 10 alphabetically: `agentforce-adlc`, `ai-plugins`, `altimate-code`, `aws-core`,
`aws-serverless`, `aws-startup-advisor`, `azure`, `carta-cap-table`, `carta-crm`, `carta-investors`.

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
| official | agentforce-adlc | 2 (PreToolUse, PostToolUse) | PASSED | 4/4 | True | 26.6 / 28.0 | 29,625 | python3 |
| official | ai-plugins | 4 (PreToolUse, PostToolUse×2, UserPromptSubmit) | PASSED | 4/4 | True | 30.6 / 33.6 | 2,289 | bash |
| official | altimate-code | 1 (SessionStart only) | NotApplicable — no hook on PreToolUse | — | — | NotApplicable | 3,940 | — |
| official | aws-core | 0 found (see note) | NotApplicable — declares no hooks | — | — | NotApplicable | 57,466 | — |
| official | aws-serverless | 1 (PostToolUse only) | NotApplicable — no hook on PreToolUse | — | — | NotApplicable | 20,523 | — |
| official | aws-startup-advisor | 1 (SessionStart only) | NotApplicable — no hook on PreToolUse | — | — | NotApplicable | 43,041 | — |
| official | azure | 0 found (see note) | NotApplicable — declares no hooks | — | — | NotApplicable | 74,359 | — |
| official | carta-cap-table | 9 (SessionStart×3, PreToolUse×2, UserPromptSubmit, PostToolUse×2, PostModelSwitch) | PASSED | 4/4 | False | Error: exit 126, not executable | 127,818 | sh (see note) |
| official | carta-crm | 7 (SessionStart×3, PreToolUse×2, UserPromptSubmit, PostModelSwitch) | PASSED | 4/4 | False | Error: exit 126, not executable | 44,588 | sh (see note) |
| official | carta-investors | 8 (SessionStart×3, PreToolUse×2, UserPromptSubmit, PostModelSwitch, PostToolUse) | PASSED | 4/4 | False | Error: exit 126, not executable | 146,663 | sh (see note) |
| wshobson-agents | protect-mcp | 2 (PreToolUse, PostToolUse) | PASSED | 4/4 | True | 664.6 / 717.5 | 1,845 | sh → npx (node) |
| wshobson-agents | review-agent-governance | 2 (PreToolUse, PostToolUse) | PASSED | 4/4 | True | 666.7 / 711.2 | 1,634 | sh → npx (node) |
| othmanadi-planning-with-files | planning-with-files | 6 (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PreCompact, Stop) | FAILED | 0/4 | True | Error: exit 127, command not found (see note) | 25,179 | sh (see note) |
| official | 42crunch-api-security-testing | 0 | NotApplicable — declares no hooks | — | — | NotApplicable | 17,912 | — |
| official | activecampaign | 0 | NotApplicable — declares no hooks | — | — | NotApplicable | 9,069 | — |
| official | adobe-for-creativity | 0 | NotApplicable — declares no hooks | — | — | NotApplicable | 43,647 | — |
| official | agent-sdk-dev | 0 | NotApplicable — declares no hooks | — | — | NotApplicable | NotApplicable (no text files) | — |
| official | aikido | 0 | NotApplicable — declares no hooks | — | — | NotApplicable | 1,509 | — |

## What the rows say

**A discovery gap: a `hooks` field that is not a fixed path.** v0.1's plugin-hook discovery
(`discover.py`) reads exactly one location, `<plugin>/hooks/hooks.json`, and never consults the
plugin's own `.claude-plugin/plugin.json`, which can carry a `hooks` field pointing anywhere else.
Six plugins in the official marketplace use that field to point elsewhere —
`aws-core` (`./com.anthropic.claude-code/hooks/hooks.json`), `azure`
(`./hooks/claude-hooks.json`), `data-agent-kit-starter-pack`, `dash0`, `sonarqube`
(`./claude-hooks/hooks.json`), `spotify-ads-api` — and for two of them, `aws-core` and `azure`, we
picked up the discovery gap by drawing them into the sample under the alphabetical tie-break. Both
report `NotApplicable — the plugin declares no hooks` even though their own manifests declare one;
the row is honest about what v0.1 measured (nothing), but "declares no hooks" reads as a claim
about the plugin when it is really a claim about the producer's fixed search path. `sonarqube`
alone runs a hook on `SessionStart` from that non-default file — this is not a hypothetical case.

**A discovered hook can still be the wrong one: `args` is dropped.** `planning-with-files`'
`hooks.json` uses a `{"command": "sh", "args": [...]}` shape — the actual script path and mode
argument live in `args`, not `command`. `discover.py`'s `_commands_in_entry` reads only `command`,
so the hook the producer drives is the bare string `sh` with no arguments at all, not
`sh "${CLAUDE_PLUGIN_ROOT}/hooks/claude-hook.sh" pre-tool-use`. Every invocation resolves to the
interactive shell reading from a closed stdin and exiting immediately (`sh: 1: {hook_event_name}:
not found` on stderr — the shell trying to interpret the JSON payload as a command once stdin is
attached), so `reachability` reports `FAILED` from all four directories and latency is
`Error: exit 127`. The plugin's real hook script was never exercised; this is a producer coverage
gap for a second real, widely-installed marketplace, not evidence about `claude-hook.sh` itself.

**Reachable is not executable.** `carta-cap-table`, `carta-crm`, and `carta-investors` share one
dispatch shim, `hooks/dispatch.sh`, invoked directly from `hooks.json` (no `bash`/`sh` in front of
the command). Its git blob is committed as `100644` (no execute bit) in all three plugin
directories — the same blob, `43ec749b…`, in each. `reachability` still reports `PASSED` from all
four directories, because reachability asks only whether the client's plugin-root variable resolves
the client to *some* file at that path (as opposed to "no such file or directory"); it is
`fault.malformedOutput`'s `wouldAllowAny: False` and `cost.latency_ms`'s `Error: exit 126, not
executable` that catch the file existing but never running. The three rows agree with each other
and disagree with what "reachable" suggests on its own — a reader taking the reachability row alone
would conclude the hook runs, and it does not.

**`npx` is a two-order-of-magnitude latency cost.** `protect-mcp` and `review-agent-governance`
(both `wshobson/agents`) invoke `npx protect-mcp@0.7.4 …` from their `PreToolUse` hook. p50 is
664.6 ms and 666.7 ms — roughly 20–25× the 26–34 ms p50 of the plugins that shell out to a local
`python3`/`bash` script directly. The row does not say why; `npx` resolving and starting a
published npm package on every tool call is the visible mechanism, not a claim this predicate
measures.

**A first measurement can move the subject out from under itself — and the producer refuses to
proceed.** The first `produce` run against `agentforce-adlc` failed outright
(`error: a producer changed the subject while measuring it; refusing to bind a statement to an
artifact that no longer matches what the user has`) rather than emitting a statement. Its
`PreToolUse` hook script imports a sibling module; running it for the first time made CPython write
`shared/hooks/scripts/__pycache__/stdin_utils.cpython-311.pyc` into the plugin's own directory,
changing the subject's digest mid-measurement. The producer's own before/after digest check caught
this and refused rather than silently binding to a stale digest — the correct behaviour, and the
row this sample carries for `agentforce-adlc` is from the second attempt, after the cache file
already existed and the subject was stable across the run. A producer measuring a fresh checkout of
this plugin for the first time will see the same refusal.

**Every measured hook exits with something other than a silent allow on malformed input, except
where the file cannot run at all.** Of the seven plugins with a measured `PreToolUse` hook,
`wouldAllowAny` is `True` for four (`agentforce-adlc`, `ai-plugins`, `protect-mcp`,
`review-agent-governance`) and `False` for the three `carta-*` plugins — for the reason above, not
because those hooks evaluated the malformed input and denied it.

**Context weight varies by two orders of magnitude and mostly reflects file count, not hooks.**
The smallest bundle in the sample (`review-agent-governance`, 1,634 tokens under `approx-regex-v1`)
and the largest (`carta-cap-table`, 127,818) are both hook-bearing; the no-hook plugins range from
1,509 (`aikido`) to 74,359 (`azure`) tokens. `agent-sdk-dev` has no skill or hooks text at all —
`cost.context_tokens` reports `NotApplicable: no text files to count`, not zero.

No plugin in this sample is named here as broken, misconfigured, or unsafe: every `Error` and
`NotApplicable` row above states what v0.1 measured and why it stopped there, per the reasoning the
statement itself carries. Whether any of these facts crosses a catalog's own bar is the catalog's
threshold to set, not this report's.

## Reproduce

```bash
pip install -e /path/to/context-report          # base install, no [efficacy] extra needed
git clone https://github.com/<owner>/<repo> <dest> && git -C <dest> checkout <commit>   # per inventory.json
context-report produce --subject <plugin dir> --kind plugin --target claude_code --n 20 \
  --out paper/measurements/catalog-sample/<marketplace>/<plugin>.json
context-report verify paper/measurements/catalog-sample/<marketplace>/<plugin>.json --subject <plugin dir>
```

`inventory.json` lists, per plugin, the marketplace, repo URL, path inside the repo, commit, and
subject digest recorded in its statement; re-cloning at that commit and re-running `produce` should
reproduce every re-derivable row (`reachability`, `fault.malformedOutput`,
`cost.context_tokens`) exactly and `cost.latency_ms` as a comparable distribution.
