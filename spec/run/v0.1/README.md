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
  Each entry is `{id, path, kind}`: `id` is the handle a task's `subjects`/`rules` fields use to
  name this artifact and defaults to the path's basename; `path` is where the artifact lives on
  disk; `kind` is one of the six `subjectKind` values the attestation predicate recognizes
  (`plugin`, `instruction-file`, `skill`, `hook`, `mcp-server`, `subagent`). Subject ids MUST be
  unique within a manifest.
- **`target`** — the agent every statement produced from this manifest is about, `{name,
  clientVersion}` — the same shape as the predicate's own `target` field. To compare two agents,
  run the manifest twice with a different `target.name`; this schema deliberately has no field for
  a second agent in the same run.
- **`models`** — the subject models to run the paired ablation on, `[{provider, id}, ...]`. An
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
- **`judge`** — `null`, or a `{provider, id}` model reference: the one model that grades every
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

## What this manifest deliberately does not contain

- **Prices.** A row records tokens; what a token costs is a catalog's own arithmetic over its own
  contract, not a fact this format states.
- **Thresholds.** Nothing here says what lift, what latency, or what interval width is acceptable.
  A manifest produces facts; a consumer's own policy decides what passes.
- **A hooks block.** A plugin's hooks are read from the plugin's own hooks manifest at the target
  agent's own hook-registration location, never supplied by the caller. Letting a manifest declare
  hooks here would let it assert hooks the plugin does not actually register — precisely the gap a
  `reachability` row exists to catch.

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
