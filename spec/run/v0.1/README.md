# context-report run manifest v0.1

This is the normative specification for `context-report run`'s input: a manifest naming which
artifacts to measure, against which agent, with which subject models, over which tasks, and how
many runs per arm. The JSON Schema at [`schema.json`](schema.json) is authoritative; this document
explains what each field means. Where the two disagree, the schema wins and this file has a bug.

## Purpose

A run manifest turns an `efficacy` claim (see
[`../../attestation/v0.1/attributes.md`](../../attestation/v0.1/attributes.md#efficacy)) from a
one-off script into a reproducible design: the same manifest, run again with the same `seed`,
exercises the same subjects over the same tasks with the same arm counts against the same target.
It is metadata only — how an artifact actually works (what a plugin's hooks are, what an
`AGENTS.md` says) is read from the artifact itself, never declared here.

## Top-level fields

- **`contextReportRun`** — always `"v0.1"`. Pins the manifest to this schema version, the way
  `predicateType` pins a statement (see the attestation README's Versioning section).
- **`subjects`** — the artifacts under test. One statement is produced per `(subject, model)` pair.
  Each entry is `{id, path, kind, workdir?}`: `id` is the handle a task's `subjects`/`rules` fields use to
  name this artifact and defaults to the path's basename; `path` is where the artifact lives on
  disk; `kind` is one of the six `subjectKind` values the attestation predicate recognizes
  (`plugin`, `instruction-file`, `skill`, `hook`, `mcp-server`, `subagent`). Subject ids MUST be
  unique within a manifest.
  `workdir` (optional, relative to the manifest) is the directory the subject model works in for
  this subject's tasks — normally the checkout the instruction file belongs to, so a task like
  "add this dependency" sees the repository's `package.json`. Without it the model works in the
  directory the run was started from, and answers about "this repo" describe that directory.
  Only the `claude-cli` provider can honour it; a manifest that sets one and names an `anthropic`
  model is rejected before any call.
- **`target`** — the agent every statement produced from this manifest is about, `{name,
  clientVersion}` — the same shape as the predicate's own `target` field. To compare two agents,
  run the manifest twice with a different `target.name`; this schema deliberately has no field for
  a second agent in the same run.
- **`models`** — the subject models to run the paired ablation on, `[{provider, id}, ...]`. Two
  providers have a backend in v0.1: `anthropic` (the API; `id` is a model id) and `claude-cli`
  (the local `claude` CLI under its own login; `id` is an alias such as `opus`, `sonnet`, `fable`,
  or a full id), so one manifest can list the same rules against several models. An
  empty array means the run produces only deterministic rows (`reachability`, `fault.*`,
  `cost.context_tokens`, ...) and no `efficacy` row — there is no subject model to ablate. When
  `models` is non-empty, `tasks` is required (the schema enforces this): a model with nothing to
  run against it is a manifest that cannot proceed.
- **`tasks`** — either a path to a tasks file (a string, resolved relative to the manifest) or the
  tasks given inline as `{"tasks": [...]}`. The same task set is used for every model named in
  `models`. See Tasks below.
- **`arms`** — `{nPerArm, seed, mode}`. `nPerArm` is how many times each task is run in each arm
  (once with the rule, once without). `seed` fixes task order and any sampling so a re-run of the
  same manifest reproduces the same trials. `mode` is `"isolated"` (default) — each subject is
  measured alone against the bare agent, one subject's rule at a time — or `"leave-one-out"`: all
  subjects installed together, each ablated in turn while the others stay in place. v0.1's schema
  accepts `"leave-one-out"` but does not implement it; a manifest naming it today has nothing that
  runs it.
- **`judge`** — `null`, or a `{provider, id}` model reference (same two providers): the one model that grades every
  recorded transcript, for every subject model, in this run. Holding the judge fixed while subject
  models vary is what makes an efficacy comparison across models fair — see "Two models, not one"
  in the attestation attribute registry. `null` means no model grades anything; a rule with a
  machine-checkable criterion is still graded by code (`judge: "deterministic"` in the resulting
  row's `conditions`), and every other rule surfaces under that row's `values.ungraded`, never
  guessed at.
- **`out`** — the output directory. MUST NOT be inside, or contain, any subject's own path:
  writing run output into a subject would change that subject's digest out from under the very run
  that is measuring it.

## Tasks

A task is `{id, prompt, subjects?, rules?, criteria?}`:

- **`id`** — unique within the manifest.
- **`prompt`** — what the agent is asked to do. It should tempt a violation of the rule(s) it
  exercises; a task nobody could fail either way measures nothing.
- **`subjects`** — which subjects (by id) this task exercises. Default: every subject in the
  manifest — a task naming no subjects is "applies to all", not "applies to none".
- **`rules`** — which rule ids, within the named subjects, this task exercises. Default: every
  rule those subjects declare. A rule that no task in the manifest names gets no card at all when
  the run builds its cards: it is reported as unexercised, never silently scored as passing.
- **`criteria`** — per rule id, what compliance looks like for this specific task. Default: the
  rule's own text. This is what lets one rule ("never commit secrets") be graded against a
  task-specific standard ("the API key sk-live-... never lands in a committed file") instead of
  a judge re-reading the abstract rule text on every task.

## Tasks as eval cases

`tasks` may instead name a directory: the `claude plugin eval` case layout plugin developers
already write, from Claude Code's early-access reference. `context_report.run.evalcases` compiles
it into exactly the task list above — **the JSON tasks file above is the compiled form**; nobody
is expected to hand-write it. [`examples/evals/`](examples/evals/) is a worked example; the
worked `run.json` points `tasks` at it.

```
<tasks-dir>/                      # the manifest's `tasks` value, e.g. "evals"
  <case-name>/
    prompt.md                     # YAML frontmatter + the prompt body
    graders/<grader-name>.md      # YAML frontmatter with `type` + fields; body may hold a rubric
    case.yaml                     # optional: setup, history replay — ignored in v0.1
  mocks/<server>/<tool>.md        # optional — ignored in v0.1
```

One case directory is one task; its directory name is the task's `id`. `prompt.md` and each
grader file are parsed as YAML frontmatter (the block between the first two `---` lines) followed
by a body; a missing or malformed frontmatter block is a manifest error naming the file.

| Case field | Task field | Notes |
|---|---|---|
| `prompt.md` body | `prompt` | Frontmatter stripped, whitespace trimmed. |
| `prompt.md` frontmatter `plugins` | `subjects` | Each entry is a path relative to the case directory, resolved and matched against a subject's own resolved `path`. A `plugins` entry matching no subject is a manifest error naming both the entry and the known subjects. No `plugins` → every subject, same as a JSON task with no `subjects`. |
| `prompt.md` frontmatter `tags` | `rules` + `tags` | A tag of the form `rule:<id>` contributes `<id>` to `rules`; every other tag is kept verbatim on the new `Task.tags` (the v0.1 runner ignores it). |
| `prompt.md` frontmatter `runs` | `runs` | Recorded on the new `Task.runs`. **`arms.nPerArm` is still what v0.1 runs** — a per-case `runs` is honoured only by the vendor's own runner. |
| `graders/*.md` with `type: llm` | `criteria` | The grader's `criteria` text binds to the rule id in its own `rule:` frontmatter field if it has one; otherwise to every rule id the case names via `rule:` tags; otherwise (no `rule:` tags at all) it is kept under the key `"*"`. |
| `graders/*.md` with `type: regex` and `target: last_message` (or no `target`) | — | Compiled to a deterministic `Checker` (`GraderRegex` in `efficacy/fastjudge.py`), not into `criteria`. `context_report.run.evalcases.checkers_for(tasks)` builds them; wiring them into `efficacy.grade.grade` is left to whoever assembles the run (see below). |
| everything else | `vendor_graders` | `type: tool_used`, `tool_order`, `file_exists`, `baseline`; a `regex` grader whose `target` is not `last_message` (e.g. `mock_calls`, `trace`, `files`). v0.1's runner is single-turn with no tool trace, filesystem diff, or baseline run to check these against, so they are recorded on the new `Task.vendor_graders` (so a row can say which graders it skipped) rather than errored on. |
| `case.yaml`, `mocks/` | — | Ignored in v0.1 (setup/history replay and mock tool responses need a multi-turn vendor runner); their presence must not raise an error. |
| `prompt.md` frontmatter `name`, `max_turns`, `timeout_seconds`, `allowed_tools`, `model`, `append_system_prompt`, `env` | — | Vendor-runner-only: v0.1 runs one prompt against one target agent per manifest, so there is no per-case turn budget, tool allowlist, or model override to carry. `name` is not used either — the case *directory name* is the task `id`. |

**The `criteria["*"]` key is an extension of `cards_for`'s consumer contract**
(`src/context_report/run/cards.py`): it means "the default criterion for every rule of this
task's named subjects that has no more specific entry". `cards_for` does not read it as of this
writing — it resolves a scenario's criterion as `task.criteria.get(rule.id, rule.text)` — so an
eval case with `llm` graders but no `rule:` tags gets the rule's own text as its criterion until
`cards_for` is extended to fall back to `criteria.get("*")` before `rule.text`.

## What this manifest deliberately does not contain

- **Prices.** A row records tokens; what a token costs is a catalog's own arithmetic over its own
  contract, not a fact this format states.
- **Thresholds.** Nothing here says what lift, what latency, or what interval width is acceptable.
  A manifest produces facts; a consumer's own policy decides what passes.
- **A hooks block.** A plugin's hooks are read from the plugin's own hooks manifest at the target
  agent's own hook-registration location, never supplied by the caller. Letting a manifest declare
  hooks here would let it assert hooks the plugin does not actually register — precisely the gap a
  `reachability` row exists to catch.

## Resuming an interrupted run

`context-report run MANIFEST --resume` keeps whatever an earlier run left under `out`: a
`(subject, model)` pair whose statement exists is not run again, and a pair with transcripts but
no statement reuses each transcript whose `input_sha256` and model still match, calling the model
only for the trials that are missing. Without `--resume`, a run into an existing `out` records
everything afresh and overwrites.

## Output layout

Running a manifest with `"out": "reports/"` produces:

```
reports/
  manifest.json                     # the resolved manifest, for provenance
  <subject id>/
    <model slug>.json               # the statement for this subject and this model
    <model slug>/
      transcripts/                  # one file per (task, rule, arm, trial) recorded
    statement.json                  # only when `models` is empty: one deterministic statement
  SUMMARY.md                        # a human-readable table across every subject and model
```

A **model slug** is `<provider>--<id>` with every character outside `[A-Za-z0-9._-]` replaced by
`_` (e.g. `anthropic/claude-sonnet-5` slugs to `anthropic--claude-sonnet-5`) — the same rule
`ModelRef.slug` applies, so a filesystem path never needs to round-trip through JSON to be read
back.

`context-report judge OUT --judge <provider>/<id>` re-grades recorded transcripts after the fact
and writes a `.judged.json` sibling next to each statement it touches (e.g.
`<model slug>.judged.json`), rather than overwriting the original: a statement is immutable once
produced, and judging it again under a different judge is a new claim, not an edit to the old one.

## Where the arms go

See [`../../attestation/v0.1/README.md`](../../attestation/v0.1/README.md#where-the-arms-live) for
how the transcripts this layout writes relate to the `efficacy` row a statement ends up carrying.

## Versioning

Per in-toto convention, `0.X` versions are major: fields MAY be added, removed, or change meaning
between `0.1` and `0.2` without notice.
