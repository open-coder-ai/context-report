# Top-N catalog plugins, measured by context-report v0.1

18 public plugins, measured with the reference producer, `n = 20`, on 2026-09-06.

![Figure 3](../../figures/fig-catalog-status.svg)

![Figure 4](../../figures/fig-latency.svg)

## Selection

- Marketplaces: official (291 plugins) plus the two highest-starred community ones not owned by
  Anthropic (`inventory.json` has commits and stars).
- Rule, fixed first: every official hook-declaring plugin up to 10; fill to 15 from community
  marketplaces; add 5 no-hook plugins for the `NotApplicable` rows.
- Community marketplaces held only 3 hook-bearing plugins, so the sample has 13, not 15 — an
  ecosystem finding, not a search shortfall.
- 18 total: 13 hook-bearing + 5 no-hook.
- Each subject is a plugin directory at its `inventory.json` commit; repos were cloned read-only.

**Machine**: Linux-6.18.44-fc-v24-x86_64, Python 3.11.15, 4 CPUs.
**Producer**: `c285c6e`, third pass (see "Producer fixes" below).

## Results

Latency is per `PreToolUse` invocation, `n = 20`, `environmentSensitive`. "Malformed input allows"
is `fault.malformedOutput`'s `wouldAllowAny`.

| Plugin | Reachability | Allows malformed | p50 / p95 ms | Tokens |
| :--- | :--- | :--- | :--- | ---: |
| agentforce-adlc | PASSED, 4/4 | yes | 26.8 / 28.7 | 29,625 |
| ai-plugins | PASSED, 4/4 | yes | 32.0 / 37.4 | 2,289 |
| aws-core | PASSED, 4/4 | yes | 45.5 / 51.8 | 57,466 |
| planning-with-files | PASSED, 4/4 | yes | 6.0 / 6.2 | 25,179 |
| protect-mcp | PASSED, 4/4 | yes | 665.8 / 686.5 | 1,845 |
| review-agent-governance | PASSED, 4/4 | yes | 672.0 / 711.2 | 1,634 |
| carta-cap-table | FAILED, 0/4 | never ran | exit 126 | 127,818 |
| carta-crm | FAILED, 0/4 | never ran | exit 126 | 44,588 |
| carta-investors | FAILED, 0/4 | never ran | exit 126 | 146,663 |
| altimate-code, aws-serverless, aws-startup-advisor, azure | NotApplicable, no pre-tool hook | — | — | 3,940–74,359 |
| five plugins, no hooks declared | NotApplicable | — | — | 1,509–43,647; one has no text |

- **`npx` is a two-order-of-magnitude latency cost**: `protect-mcp`/`review-agent-governance` run
  665.8–672.0 ms via `npx`, against 6.0–51.8 ms for a local script.
- **Every hook that actually runs allows on malformed input** — `True` for all six timed.
- **Reachable is still not executable**: the three `carta-*` plugins share one dispatch shim with
  no execute bit; all three rows agree it never ran.
- **Context weight is unaffected by either fix**, 1,509–74,359 tokens among no-hook plugins;
  `agent-sdk-dev` has none, reported `NotApplicable`, not zero.

## Producer fixes

Three passes exist; only the third (`c285c6e`) is committed — a reader should not use numbers from
either earlier pass.

| Plugin | Pass 1 | Pass 2 (`fd746de`) | Pass 3 (`c285c6e`) |
| :--- | :--- | :--- | :--- |
| aws-core | `NotApplicable` — hooks path discovery did not yet read | fully measured | unaffected |
| azure | `NotApplicable — declares no hooks` | `NotApplicable` for the true reason: one hook, on `PostToolUse` | unaffected |
| carta-cap-table, carta-crm, carta-investors | `reachability: PASSED (4/4)` | `FAILED (0/4)` — shared `dispatch.sh` has no execute bit | unaffected |
| agentforce-adlc | first attempt failed — hook's `__pycache__` write moved the subject digest | fixed via `PYTHONDONTWRITEBYTECODE=1` | unaffected |
| planning-with-files | (baseline) | numbers spurious: `shlex.quote()` over-quoted a var, hook never opened, yet read `PASSED` | `PASSED (4/4)` for the real reason; 6.0/6.2 ms, fastest in the sample |

Each gap has a named test. No plugin here is named as broken or unsafe: every row states what
v0.1 measured and why; crossing a catalog's bar is the catalog's threshold, not this report's.

## Reproduce

```bash
pip install -e /path/to/context-report          # base install, no [efficacy] extra needed; at c285c6e or later
git clone https://github.com/<owner>/<repo> <dest> && git -C <dest> checkout <commit>   # per inventory.json
context-report produce --subject <plugin dir> --kind plugin --target claude_code --n 20 \
  --out paper/measurements/catalog-sample/<marketplace>/<plugin>.json
context-report verify paper/measurements/catalog-sample/<marketplace>/<plugin>.json --subject <plugin dir>
```

`inventory.json` lists, per plugin, the marketplace, repo URL, path, commit, and subject digest.
Re-cloning at that commit and re-running `produce` at or after `c285c6e` reproduces every
re-derivable row exactly and `cost.latency_ms` as a comparable distribution; an earlier producer
reproduces one of the two misreported passes above, not these rows.
