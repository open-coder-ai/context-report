# Top-N catalog plugins, measured by context-report v0.1

The paper's §5.2 sample: 18 public Claude Code plugins, chosen by a rule fixed before looking at
any measurement (see "Selection" below), measured with the reference producer, `n = 20` latency
samples, on 2026-09-06.

**Machine**: Linux-6.18.44-fc-v24-x86_64, Python 3.11.15, 4 CPUs.

**Producer version**: `fd746de2a13b46b6f966114c168221248f43fad5`
("produce: read manifest-declared hooks files and args; exit 126 is unreachable; no bytecode in
the subject", `open-coder-ai/context-report#18`). This supersedes the first pass, run on the
producer's `main` before that fix (`85cce038…`-era `context-report`); three of this sample's own
findings from that first pass are what the fix addresses — see "What changed from the first pass"
below.

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
| official | agentforce-adlc | 2 (PreToolUse, PostToolUse) | PASSED | 4/4 | True | 26.6 / 27.5 | 29,625 | python3 |
| official | ai-plugins | 4 (PreToolUse, PostToolUse×2, UserPromptSubmit) | PASSED | 4/4 | True | 31.7 / 33.1 | 2,289 | bash |
| official | altimate-code | 1 (SessionStart only) | NotApplicable — no hook on PreToolUse | — | — | NotApplicable | 3,940 | — |
| official | aws-core | 2 (PreToolUse×2) | PASSED | 4/4 | True | 45.8 / 49.4 | 57,466 | python3 |
| official | aws-serverless | 1 (PostToolUse only) | NotApplicable — no hook on PreToolUse | — | — | NotApplicable | 20,523 | — |
| official | aws-startup-advisor | 1 (SessionStart only) | NotApplicable — no hook on PreToolUse | — | — | NotApplicable | 43,041 | — |
| official | azure | 1 (PostToolUse only) | NotApplicable — no hook on PreToolUse | — | — | NotApplicable | 74,359 | — |
| official | carta-cap-table | 9 (SessionStart×3, PreToolUse×2, UserPromptSubmit, PostToolUse×2, PostModelSwitch) | **FAILED** | 0/4 | False | Error: exit 126, not executable | 127,818 | sh (see note) |
| official | carta-crm | 7 (SessionStart×3, PreToolUse×2, UserPromptSubmit, PostModelSwitch) | **FAILED** | 0/4 | False | Error: exit 126, not executable | 44,588 | sh (see note) |
| official | carta-investors | 8 (SessionStart×3, PreToolUse×2, UserPromptSubmit, PostModelSwitch, PostToolUse) | **FAILED** | 0/4 | False | Error: exit 126, not executable | 146,663 | sh (see note) |
| wshobson-agents | protect-mcp | 2 (PreToolUse, PostToolUse) | PASSED | 4/4 | True | 676.4 / 708.9 | 1,845 | sh → npx (node) |
| wshobson-agents | review-agent-governance | 2 (PreToolUse, PostToolUse) | PASSED | 4/4 | True | 682.0 / 727.5 | 1,634 | sh → npx (node) |
| othmanadi-planning-with-files | planning-with-files | 6 (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, PreCompact, Stop) | **PASSED (see note)** | 4/4 | False | Error: no run exited 0 (see note) | 25,179 | sh (see note) |
| official | 42crunch-api-security-testing | 0 | NotApplicable — declares no hooks | — | — | NotApplicable | 17,912 | — |
| official | activecampaign | 0 | NotApplicable — declares no hooks | — | — | NotApplicable | 9,069 | — |
| official | adobe-for-creativity | 0 | NotApplicable — declares no hooks | — | — | NotApplicable | 43,647 | — |
| official | agent-sdk-dev | 0 | NotApplicable — declares no hooks | — | — | NotApplicable | NotApplicable (no text files) | — |
| official | aikido | 0 | NotApplicable — declares no hooks | — | — | NotApplicable | 1,509 | — |

## What changed from the first pass

The first (pre-fix) run of this same sample misreported four plugins; a reader of the paper should
use the rows above, not the ones from that run.

- **`aws-core`** previously read `NotApplicable — the plugin declares no hooks`. It declares two
  `PreToolUse` hooks through `.claude-plugin/plugin.json`'s `hooks` field
  (`./com.anthropic.claude-code/hooks/hooks.json`), which the fixed discovery now reads; it is now
  fully measured: reachable 4/4, `wouldAllowAny: True`, p50/p95 45.8/49.4 ms.
- **`azure`** previously read `NotApplicable — the plugin declares no hooks`, for the same reason as
  `aws-core` (its `hooks` field points at `./hooks/claude-hooks.json`). The fixed discovery now
  finds that file too — but its one hook is on `PostToolUse`, not `PreToolUse`, so the row is still
  `NotApplicable`, now correctly reasoned as "declares hooks, but none on claude_code's pre-tool
  event" rather than "declares no hooks." This is not a regression in the fix; it is what the
  plugin actually declares.
- **`carta-cap-table`, `carta-crm`, `carta-investors`** previously read `reachability: PASSED (4/4)`
  even though their shared `hooks/dispatch.sh` has no execute bit and never ran (caught only by
  `fault.malformedOutput`/`cost.latency_ms`, both of which saw exit 126 both times). Exit 126 now
  counts as unreachable, so all three now read `reachability: FAILED (0/4)` — the row a reader
  would actually want, since the earlier "reachable" was true only of the path resolving, not of
  anything running.
- **`agentforce-adlc`** previously required two `produce` attempts: the first failed outright
  (the plugin's own hook wrote `__pycache__` into itself, moving the subject digest mid-run) and
  only the second, with the cache file already primed, produced a statement. With hooks now run
  under `PYTHONDONTWRITEBYTECODE=1` (recorded in the row's `environment`), the very first attempt
  this time produced a statement directly; no leftover `__pycache__` was written by this run
  (a stale copy from the earlier session's first attempt was already on disk and untouched).

All four affected statements have been fully regenerated on the fixed producer; the versions
committed here are the only ones in this repository.

## What the rows say

**A discovery gap remains: `${VAR}` expansion inside a quoted `args` entry.** The fix joins a
hook's `command` and `args` with `shlex.quote()` on each argument — correct against shell
injection, but it defeats `${CLAUDE_PLUGIN_ROOT}`-style expansion for any argument that is itself a
variable reference, because a single-quoted string suppresses all shell expansion. `planning-with-files`'
one `PreToolUse` hook is exactly this shape (`{"command": "sh", "args":
["${CLAUDE_PLUGIN_ROOT}/hooks/claude-hook.sh", "pre-tool-use"]}`); the producer now runs
`sh '${CLAUDE_PLUGIN_ROOT}/hooks/claude-hook.sh' pre-tool-use` — the literal, unexpanded string —
and `dash` (this machine's `/bin/sh`) reports `cannot open ${CLAUDE_PLUGIN_ROOT}/hooks/claude-hook.sh:
No such file`. That phrasing does not match any of `reachability.py`'s
`_NOT_FOUND_STDERR_FRAGMENTS` (`"can't open file"`, `"No such file or directory"`, `"not found"` —
dash says "cannot open", not "can't open", and omits "or directory"), so `_is_unreachable` returns
`False` and the row reads `reachability: PASSED (4/4)` for a hook that never opened its script
either before or after the fix. `fault.malformedOutput` catches the same exit-2/"No such file"
result on all four cases (`wouldAllowAny: False`), and `cost.latency_ms` is honestly `Error: no run
exited 0`, so the plugin's real hook behaviour is still not observed. This is a second, narrower
instance of the args-shape gap the fix addressed, not evidence about `claude-hook.sh` itself — see
`open-coder-ai/context-report#18` (or its successor) for whether `${VAR}`-shaped `args` entries
should skip quoting, and `reachability.py`'s stderr-fragment list for the shell-wording gap.

**`npx` is still a two-order-of-magnitude latency cost.** `protect-mcp` and `review-agent-governance`
(both `wshobson/agents`) invoke `npx protect-mcp@0.7.4 …` from their `PreToolUse` hook: p50 676.4 ms
and 682.0 ms, against 26.6–49.4 ms p50 for the three plugins that shell out to a local
`python3`/`bash` script directly. Unchanged by the producer fix, since none of the three fixes touch
timing.

**Every measured hook that actually runs exits with something other than a silent allow on
malformed input.** Of the five plugins whose `PreToolUse` hook actually ran and was timed
(`agentforce-adlc`, `ai-plugins`, `aws-core`, `protect-mcp`, `review-agent-governance`),
`wouldAllowAny` is `True` for all five. The three `carta-*` plugins and `planning-with-files` all
read `wouldAllowAny: False` too, but for the reasons above (missing exec bit; `${VAR}` quoting) —
their hooks never ran either, not because they evaluated the malformed input and denied it.

**Context weight is unaffected by any of this and unchanged from the first pass.** It is computed
from the plugin's skill/manifest text files, not from running any hook, so `cost.context_tokens`
did not move for any of the 18 plugins between the two producer versions. The smallest bundle in
the sample (`review-agent-governance`, 1,634 tokens under `approx-regex-v1`) and the largest
(`carta-cap-table`, 127,818) are both hook-bearing; the no-hook plugins range from 1,509 (`aikido`)
to 74,359 (`azure`) tokens. `agent-sdk-dev` has no skill or hooks text at all —
`cost.context_tokens` reports `NotApplicable: no text files to count`, not zero.

No plugin in this sample is named here as broken, misconfigured, or unsafe: every `Error` and
`NotApplicable` row above states what v0.1 measured and why it stopped there, per the reasoning the
statement itself carries. Whether any of these facts crosses a catalog's own bar is the catalog's
threshold to set, not this report's.

## Reproduce

```bash
pip install -e /path/to/context-report          # base install, no [efficacy] extra needed; at fd746de or later
git clone https://github.com/<owner>/<repo> <dest> && git -C <dest> checkout <commit>   # per inventory.json
context-report produce --subject <plugin dir> --kind plugin --target claude_code --n 20 \
  --out paper/measurements/catalog-sample/<marketplace>/<plugin>.json
context-report verify paper/measurements/catalog-sample/<marketplace>/<plugin>.json --subject <plugin dir>
```

`inventory.json` lists, per plugin, the marketplace, repo URL, path inside the repo, commit, and
subject digest recorded in its statement; re-cloning at that commit and re-running `produce` on a
producer at or after `fd746de` should reproduce every re-derivable row (`reachability`,
`fault.malformedOutput`, `cost.context_tokens`) exactly and `cost.latency_ms` as a comparable
distribution. Running against a producer before `fd746de` reproduces the misreported first-pass
rows described above, not these.
