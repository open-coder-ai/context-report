# Top-N catalog plugins, measured by context-report v0.1

18 public plugins, measured with the reference producer, `n = 20`, on 2026-09-06.

![Figure 4](../../figures/fig-catalog-status.svg)

![Figure 5](../../figures/fig-latency.svg)

## Selection

- Marketplaces: official (291 plugins) plus the two highest-starred community ones not owned by
  Anthropic.
- Rule, fixed first: every official hook-declaring plugin up to 10; fill to 15 from community
  marketplaces; add 5 no-hook plugins for the `NotApplicable` rows.
- Community marketplaces held only 3 hook-bearing plugins, so the sample has 13, not 15 — an
  ecosystem finding.
- 18 total: 13 hook-bearing + 5 no-hook.
- Each subject is a plugin directory at its `inventory.json` commit, cloned read-only.

**Machine**: Linux-6.18.44-fc-v24-x86_64, Python 3.11.15, 4 CPUs.
**Producer**: `a8bab38`, fourth pass, 2026-09-06 (see "Producer fixes" below).

## Results

Latency is per `PreToolUse` invocation, `n = 20`, `environmentSensitive`. "Malformed input allows"
is `fault.malformedOutput`'s `wouldAllowAny`.

| Plugin | Reachability | Allows malformed | p50 / p95 ms | Tokens |
| :--- | :--- | :--- | :--- | ---: |
| agentforce-adlc | PASSED, 4/4 | yes | 33.1 / 36.1 | 29,625 |
| ai-plugins | PASSED, 4/4 | yes | 38.9 / 45.7 | 2,289 |
| aws-core | PASSED, 4/4 | yes | 53.9 / 60.2 | 57,466 |
| planning-with-files | PASSED, 4/4 | yes | 7.3 / 7.5 | 25,179 |
| protect-mcp | PASSED, 4/4 | yes | 941.5 / 1041.3 | 1,845 |
| review-agent-governance | PASSED, 4/4 | yes | 916.8 / 950.2 | 1,634 |
| carta-cap-table | FAILED, 0/4 | never ran | exit 126 | 127,818 |
| carta-crm | FAILED, 0/4 | never ran | exit 126 | 44,588 |
| carta-investors | FAILED, 0/4 | never ran | exit 126 | 146,663 |
| altimate-code, aws-serverless, aws-startup-advisor, azure | NotApplicable, no pre-tool hook | — | — | 3,940–74,359 |
| five plugins, no hooks declared | NotApplicable | — | — | 1,509–43,647; one has no text |

- **`npx` is a two-order-of-magnitude latency cost**: `protect-mcp`/`review-agent-governance` run
  916.8–941.5 ms via `npx`, against 7.3–53.9 ms for a local script.
- **Every hook that runs allows malformed input** — `True` for all six timed.
- **Reachable is still not executable**: the three `carta-*` plugins share one dispatch shim with
  no execute bit; all three rows agree.
- **Context weight is unaffected by either fix**, 1,509–74,359 tokens among no-hook plugins;
  `agent-sdk-dev` has none: `NotApplicable`, not zero.

## Producer fixes

Four passes exist; only the fourth (`a8bab38`) is committed — do not use earlier numbers.

| Plugin | Pass 1 | Pass 2 (`fd746de`) | Pass 3 (`c285c6e`) | Pass 4 (`a8bab38`) |
| :--- | :--- | :--- | :--- | :--- |
| aws-core | `NotApplicable` — hooks path discovery did not yet read | fully measured | unaffected | |
| azure | `NotApplicable — declares no hooks` | `NotApplicable` for the true reason: one hook, on `PostToolUse` | unaffected | |
| carta-cap-table, carta-crm, carta-investors | `reachability: PASSED (4/4)` | `FAILED (0/4)` — shared `dispatch.sh` has no execute bit | unaffected | |
| agentforce-adlc | first attempt failed — hook's `__pycache__` write moved the subject digest | fixed via `PYTHONDONTWRITEBYTECODE=1` | unaffected | |
| planning-with-files | (baseline) | numbers spurious: `shlex.quote()` over-quoted a var, hook never opened, yet read `PASSED` | `PASSED (4/4)` for the real reason; 6.0/6.2 ms, fastest in the sample | |
| all eighteen | | | | `cost.context_tokens` keyed `per_file` by absolute clone path and hashed it into `inputHash`; fixed in #27; this pass re-measured on it. |

Each gap has a named test. No plugin is named broken or unsafe; crossing a catalog's bar is the
catalog's threshold, not this report's.

## Reproduce

```bash
pip install -e /path/to/context-report          # base install; a8bab38 or later
git clone https://github.com/<owner>/<repo> <dest> && git -C <dest> checkout <commit>   # per inventory.json
context-report produce --subject <plugin dir> --kind plugin --target claude_code --n 20 \
  --out paper/measurements/catalog-sample/<marketplace>/<plugin>.json
context-report verify paper/measurements/catalog-sample/<marketplace>/<plugin>.json --subject <plugin dir>
```

`inventory.json` lists, per plugin, the marketplace, repo URL, path, commit, and subject digest.
Re-cloning at that commit and re-running `produce` at or after `a8bab38` reproduces every
re-derivable row exactly and `cost.latency_ms` as a comparable distribution; an earlier producer
reproduces a superseded pass above, not these rows.
