# Attribute registry — context-report v0.1

One section per `attribute` value in [`schema.json`](schema.json)'s `$defs.attributeName` enum.
This file is the registry the schema enum is a fingerprint of: a name here without a matching
schema entry, or a schema entry without a matching section, is a bug caught by
`tests/test_spec_prose.py`. `subjectKind` applicability uses the table in
[`../../../plan/context-attestation.md`](../../../../plan/context-attestation.md) (Subject
section) — reproduced per attribute below. A `subjectKind` for which an attribute does not apply
MUST get a row with `result: "NotApplicable"` and `reasoning` naming the kind, never a silently
omitted row and never a `PASSED` standing in for "nothing to check". The schema enforces this table
at the predicate level, and the reference producer ships it as `applicability-v0.1.json`;
`tests/test_spec_prose.py` holds the three in agreement.

Vendor behaviour cited below as a check's oracle is attributed with `basis: vendor-docs` in this
document's own sense (chock's tested/witnessed/vendor-docs evidence grading) — this is a
*different* axis from the row's schema `basis` (`re-derivable`/`claimed`). Citing a vendor's
documented behaviour here says only "this is what the vendor states"; it is not itself a
measurement, and a producer's actual row for a given run is `re-derivable` because *it* rerun the
check, not because the vendor wrote a doc page about it. Source:
`../../../../discovery/2026-09-05-context-attestation-prior-art.md`.

## conformance

**Question.** Does the artifact validate against its target agent's own bundle/manifest schema
(e.g. a plugin's `.claude-plugin/plugin.json`, an MCP server's declared tool schema)?

**Applies to**: `plugin`, `instruction-file`, `skill`, `hook`, `mcp-server`, `subagent` (all six —
every kind has some vendor-defined shape it must conform to, even prose: a malformed
`AGENTS.md` front-matter block is a conformance failure). No `subjectKind` is exempt in v0.1; there
is no `NotApplicable` case for this attribute today.

**basis**: `re-derivable`. Schema validation is deterministic given the artifact and the vendor's
published schema version.

**inputHash MUST cover**: the subject digest and the exact version of the vendor schema/manifest
spec checked against (recorded via `resolvedDependencies[]`, e.g.
`pkg:npm/@copilot/plugin-schema@1.104.0`). A stale vendor schema produces a green result for a
broken artifact — the version checked against is part of what makes the row re-derivable to the
*same* answer.

**Shape**: `values` (e.g. `{"schemaVersion": "1.104.0"}`); `evidence` MAY point at the validator
output. No `measurement`/`estimate`.

**result semantics**: `PASSED` — validates. `FAILED` — does not validate; `reasoning` SHOULD
name the failing path. `WARNED` — validates, but against a deprecated schema version.

**since**: v0.1

## reachability

**Question.** Is this artifact registered where the target agent actually reads it, and does it
resolve correctly regardless of the agent's current working directory?

**Applies to**: `plugin`, `instruction-file`, `skill`, `hook`, `mcp-server`, `subagent` (all six).
For prose (`instruction-file`), this is the attribute that catches a rule written only into
`CLAUDE.md` on an agent that reads only `AGENTS.md` — the same defect class as a hook path that
only resolves from the repo root.

**basis**: `re-derivable`. Whether a given file or hook path resolves from a given `cwd` is a
deterministic fact of the artifact and the agent's documented resolution order.

**inputHash MUST cover**: the subject digest, `target.name` and `target.annotations.clientVersion`,
and the list of working directories tested (recorded in `conditions.cwdTested`).

**Shape**: `conditions.cwdTested` (an array of the working directories exercised, either paths
such as `["/", "/src", "/src/deep"]` or stable labels such as `["root", "nested", "parent",
"outside"]` when the paths are temporary); `evidence` MAY point at a reachability log. For a
multi-hook `plugin` (see below), `conditions.hooks` and `values.{reachable_from,unreachable_from,
perHook,skippedHooks}` are also present. No `measurement`/`estimate`.

**Multi-hook plugins.** A plugin's hooks are discovered from the plugin's own hooks manifest at the
target agent's own hook-registration location — never supplied by the caller, since only the
plugin itself can say what it registers. v0.1 measures reachability of the target agent's pre-tool
event only; every other hook the plugin declares is recorded, unmeasured, in
`values.skippedHooks` (an array of hook ids). Each measured hook gets its own entry in
`values.perHook`, keyed by hook id `"<event>:<index>"` (e.g. `"PreToolUse:0"` for the first
pre-tool hook) — a plugin with exactly one hook still gets exactly one key here, so a consumer
never has to special-case the single-hook shape. The row's own top-level `values.reachable_from` is
the **intersection** of every measured hook's reachable set (a `cwd` counts only if every hook
resolves from it) and `values.unreachable_from` is the **union** (any one hook failing from a `cwd`
is enough to put it there). `conditions.hooks` lists the id and command of every hook the plugin
declares, measured or skipped, so a reader can see what was and was not exercised. `result` is
`FAILED` if any measured hook fails to resolve from any tested `cwd` — a plugin is only as
reachable as its least-reachable hook.

**result semantics**: `PASSED` — resolves from every tested `cwd` (every measured hook, for a
multi-hook subject). `FAILED` — fails to resolve from at least one tested `cwd`, or any measured
hook fails anywhere (see Multi-hook plugins above); `values` or `reasoning` SHOULD name which.
`NotApplicable` never applies here in v0.1.

**since**: v0.1

## decision

**Question.** Given a declared set of inputs, does a hook or guard allow/deny exactly as its author
declared it would?

**Applies to**: `plugin`, `hook`. `NotApplicable` for `instruction-file`, `skill`, `mcp-server`,
`subagent` — nothing executable to make a decision (reasoning: `"subjectKind <kind> has nothing to
execute"`, matching the plan's draft example verbatim).

**basis**: `re-derivable`. A declared case, replayed against the same artifact and agent version,
produces the same allow/deny outcome.

**inputHash MUST cover**: the subject digest, `target` and its `clientVersion`, and the full set of
declared cases (name + input) being replayed — replaying the same case set twice must hash equal.

**Shape**: `conditions` records the declared positive/negative cases (after OpenAI's plugin-review
contract: named cases, each with an expected allow/deny); `values` records the observed
outcome per case; `evidence` MAY point at a replay trace (`byproducts` at the statement level is
the fuller trace; `evidence` here is the per-row pointer).

**result semantics**: `PASSED` — every declared case replayed to its declared outcome.
`FAILED` — at least one case replayed to a different outcome than declared; `reasoning` SHOULD
name which case.

**Proposed in v0.1, not yet exercised by any producer:** `WARNED` — replayed correctly, but a
declared case's justification (e.g. `destructiveHint`) does not match the observed behaviour.
This mirrors OpenAI's submission contract, where a reviewer rejects when an annotation does not
match behaviour; no producer has exercised this path yet.

**since**: v0.1

## fault.scriptMissing

**Question.** When the artifact's script file is absent at invocation time, does the target agent
proceed with the tool call (fail-open) or block it (fail-closed)?

**Applies to**: `plugin`, `hook`, `mcp-server`. `NotApplicable` for `instruction-file`, `skill`,
`subagent` — nothing is invoked.

**basis**: `re-derivable`. Deleting the script and observing the agent's own behaviour is a
deterministic experiment, replayable by anyone with the bundle and the agent.

**inputHash MUST cover**: the subject digest, `target` and its `clientVersion`, and the exact hook
event under test (e.g. `PreToolUse`).

**Shape**: `values.failMode`: `"fail-open"` or `"fail-closed"`. No `measurement`/`estimate`.

**result semantics**: `PASSED` means **"measured; see `values.failMode`"** — nothing more.
`fail-open` and `fail-closed` are both `PASSED` results if that is what was actually observed;
`PASSED` is never a claim that fail-open (or fail-closed) is the *good* outcome. `FAILED` is
reserved for the row itself failing to produce a determinate `failMode` (e.g. the harness hung
without timing out cleanly, or crashed outside the fault path being tested).

**Vendor oracle** (documented behaviour to compare a measured row against; `basis: vendor-docs`,
from the prior-art record — vendors do not distinguish "script missing" from "interpreter missing"
in their own docs, so the same citations apply to `fault.interpreterMissing` below):

- **Claude Code**: a hook that cannot run exits non-zero for a reason other than `2`; documented
  behaviour is "exit 2 blocks; exit 1 or any other non-zero proceeds" — i.e. fail-open for this
  case, with a notice surfaced to the user.
- **GitHub Copilot**: `preToolUse` *command* hooks are documented as **fail-closed on crash**
  ("Denied by preToolUse hook (hook errored)") — a missing script is exactly this case.
- **Cursor**: `failClosed` is a per-script option that **defaults to `false`** — fail-open unless
  the script author opts in to fail-closed.
- **Codex CLI**: unconfirmed; the prior-art sweep could not reach Codex's docs.

**since**: v0.1

## fault.interpreterMissing

**Question.** When the interpreter the script declares (e.g. `python3`, `node`) is absent on
`PATH`, does the target agent proceed with the tool call or block it?

**Applies to**: `plugin`, `hook`, `mcp-server`. `NotApplicable` for `instruction-file`, `skill`,
`subagent`.

**basis**: `re-derivable`.

**inputHash MUST cover**: the same as `fault.scriptMissing`, plus the interpreter name/version
being removed from the test environment's `PATH`.

**Shape**: `values.failMode`: `"fail-open"` or `"fail-closed"`.

**result semantics**: identical rule to `fault.scriptMissing` — `PASSED` means "measured; see
`values.failMode`", never a judgment on which mode is safer.

**Vendor oracle** (`basis: vendor-docs`): the same citations as `fault.scriptMissing` apply —
neither Claude Code's, Copilot's, nor Cursor's documentation distinguishes a missing interpreter
from a missing script; both surface to the harness as "the hook could not run". A producer SHOULD
still measure both cases independently, because the *documentation* not distinguishing them is not
proof the *implementation* treats them identically.

**since**: v0.1

## fault.timeout

**Question.** When the artifact's script exceeds the target agent's timeout, does the tool call
proceed (fail-open) or block (fail-closed)?

**Applies to**: `plugin`, `hook`, `mcp-server`. `NotApplicable` for `instruction-file`, `skill`,
`subagent`.

**basis**: `re-derivable`. A script that sleeps past the documented timeout and an observed outcome
is a deterministic experiment.

**inputHash MUST cover**: the subject digest, `target` and its `clientVersion`, the hook event
under test, and the timeout duration used to trigger the condition.

**Shape**: `values.failMode`: `"fail-open"` or `"fail-closed"`.

**result semantics**: `PASSED` means "measured; see `values.failMode`" — identical rule to the
other `fault.*` rows. This is the row where the rule matters most in practice: every vendor cited
below fails open on timeout, so a naive reader could mistake "PASSED, fail-open" for "the plugin
passed its safety check", which is exactly the misreading this spec forbids.

**Vendor oracle** (`basis: vendor-docs`, from the prior-art record):

- **Claude Code**: documented as "timeout → output discarded, tool call proceeds" — fail-open,
  explicit.
- **GitHub Copilot**: documented as **"Timeouts are always fail-open, including for `preToolUse`
  and admin-deployed policy hooks"** — fail-open, explicit and stated to hold even for
  admin-enforced policy. `github/copilot-cli` issue #2893 reports a timed-out hook is not killed
  and a later deny from it is discarded.
- **Cursor**: `failClosed` defaults to `false`; the docs do not separately call out timeout versus
  crash, so the same per-script default applies.
- **Codex CLI**: unconfirmed.

**since**: v0.1

## fault.malformedOutput

**Question.** When the artifact's hook emits output that does not parse or does not match the
target agent's expected schema, does the tool call proceed or block?

**Applies to**: `plugin`, `hook`, `mcp-server`. `NotApplicable` for `instruction-file`, `skill`,
`subagent`.

**basis**: `re-derivable`. Emitting deliberately malformed JSON from the script and observing the
outcome is deterministic and replayable.

**inputHash MUST cover**: the subject digest, `target` and its `clientVersion`, the hook event
under test, and the malformed payload used to trigger the condition.

**Shape**: `values.failMode`: `"fail-open"` or `"fail-closed"`. For a multi-hook `plugin` (see
below), `conditions.hooks` and `values.{perHook,skippedHooks,wouldAllowAny}` are also present.

**Multi-hook plugins.** As with `reachability`, a plugin's hooks come from its own hooks manifest,
never the caller, and v0.1 exercises only the target's pre-tool event; every other declared hook is
named, unmeasured, in `values.skippedHooks`. Each measured hook's own `failMode` is recorded under
`values.perHook`, keyed by hook id `"<event>:<index>"` — one key even for a single hook, so the
shape never changes between a one-hook and a many-hook plugin. `conditions.hooks` lists every
declared hook's id and command. The row adds `values.wouldAllowAny`: `true` if *any* measured
hook's malformed-output behaviour is fail-open, even when others are fail-closed — the fact a
consumer actually needs, since one fail-open hook is enough to let a malformed guard through no
matter what its siblings do.

**result semantics**: `PASSED` means "measured; see `values.failMode`" (or, for a multi-hook
subject, `values.perHook`), never a judgment call.

**Vendor oracle** (`basis: vendor-docs`, from the prior-art record):

- **Claude Code**: documented as "JSON failing schema → non-blocking" — fail-open, explicit.
- **GitHub Copilot**: no vendor documentation of malformed-output handling specifically was found
  in the prior-art sweep; Copilot's *HTTP* hooks are documented to "fail open on any network
  error", a related but distinct failure vector, cited here only as the nearest documented data
  point, not as a claim about malformed JSON. A producer MUST measure this row directly rather than
  infer Copilot's malformed-output behaviour from that citation.
- **Cursor**: no vendor documentation found; `failClosed` defaulting to `false` is the only general
  signal.
- A 142-plugin marketplace audit (cited in the prior-art record) found a `PreToolUse` guard that
  itself fails open on malformed JSON (`sys.exit(0)` on parse error), rated Critical — this is a
  finding about one plugin's own script, not a vendor harness's documented contract, and is cited
  here only to motivate why the row exists.

**since**: v0.1

## cost.latency_ms

**Question.** How much wall-clock time does this artifact add per tool call?

**Applies to**: `plugin`, `hook`, `mcp-server`. `NotApplicable` for `instruction-file`, `skill`,
`subagent` — nothing is invoked per tool call.

**basis**: `re-derivable`, and `environmentSensitive: true` MUST be set on a measured row: the
measurement procedure is deterministic, but the millisecond values it produces depend on the runner
(see README's "Re-derivable is not identical"). `environment` (at least the platform and CPU count)
MUST be recorded so a verifier compares a re-run's distribution to this one rather than expecting
the same numbers. The schema enforces both.

**inputHash MUST cover**: the subject digest, `target` and its `clientVersion`, and the number and
shape of the sampled tool calls (`measurement.n`).

**Shape**: `measurement` — `unit: "ms"`, `n` (sample count), `percentiles` (at least `"50"`,
`"95"`, `"99"`), `min`, `max`, `mean`, `stddev`. `values` is present only for a multi-hook subject
(see below); no `estimate`.

**Multi-hook plugins.** A plugin's declared hooks are discovered the same way as for
`reachability` and `fault.malformedOutput`; v0.1 measures the target's pre-tool event only, with
every other declared hook named, unmeasured, in `values.skippedHooks`, and `conditions.hooks`
listing every declared hook's id and command. The row's top-level `measurement` is the
**per-tool-call total**: the sum, across every measured hook, of that hook's own latency for one
tool call — `conditions.aggregation: "sum-across-hooks"` records which rule produced it, since a
sum is not the only aggregation a future version might choose. Each hook's own distribution lives
under `values.perHook`, keyed by hook id `"<event>:<index>"` (one key even for a single hook), in
the same `measurement` shape as the row's own top-level one. If any one hook's latency cannot be
measured, the whole row is `Error`, and `reasoning` names which hook failed — a partial sum would
understate the artifact's true cost.

**result semantics**: `PASSED` means "measured; see `measurement`" — a distribution is not
inherently a pass or fail; a consumer applies its own latency budget. `Error` — the measurement
run itself failed to complete (e.g. the harness crashed mid-sampling, or one hook's own latency
could not be measured in a multi-hook subject), with `reasoning` naming the hook if applicable.

**since**: v0.1

## cost.context_tokens

**Question.** How many tokens does this artifact add to the agent's context window?

**Applies to**: `plugin`, `instruction-file`, `skill`, `mcp-server` (tool/resource descriptions),
`subagent`. `NotApplicable` for `hook` — a hook script's own content is not injected into the
context window (only its declared trigger metadata is, which is small and vendor-fixed).

**basis**: `re-derivable`. Token count under a named, versioned tokenizer is deterministic given
the artifact's exact text.

**inputHash MUST cover**: the subject digest, the target's tokenizer name and version (recorded via
`resolvedDependencies[]`), and which surfaces were counted (e.g. system prompt injection vs. a tool
description).

**Shape**: `measurement` — `unit: "tokens"`; `n` is typically `1` for a single deterministic
count, but MAY be greater when sampling multiple injection contexts (e.g. the count varies with
how many other skills are installed alongside it). No `values`/`estimate`.

**result semantics**: `PASSED` means "measured; see `measurement.mean`" — there is no per-artifact
budget in this format; a catalog sets its own.

**since**: v0.1

## interference

**Question.** Does this artifact shadow, override, or contradict another artifact installed
alongside it in the same agent?

**Applies to**: `plugin`, `instruction-file`, `skill`, `hook`. `NotApplicable` for `mcp-server`,
`subagent` — v0.1 does not define a co-installation conflict model for these kinds.

**basis**: `re-derivable`. Given a fixed set of co-installed artifacts, whether one shadows or
contradicts another is a deterministic fact of their declared triggers/rules.

**inputHash MUST cover**: the subject digest and the digest of every co-installed artifact checked
against (an empty declared set is valid and re-derivable to "no interference found").

**Shape**: `conditions` records the co-installed artifact set checked against; `values` MAY name
the conflicting artifact and the nature of the conflict (e.g. `{"conflictsWith": "...",
"kind": "duplicate-trigger"}`). No `measurement`/`estimate`.

**result semantics**: `PASSED` — checked against a declared co-installed set, no conflict found.
`FAILED` — a conflict was found; `values`/`reasoning` SHOULD name it. `NotAvailable` — no
co-installed artifacts were declared for this run, so the check has nothing to check against (this
is the example in `examples/plugin-copilot.json`); `NotAvailable` here is not "no conflicts", it is
"conflict-freeness was not evaluated".

**since**: v0.1

## efficacy

**Question.** Does installing this artifact change what the agent does, relative to not installing
it?

**Applies to**: `plugin`, `instruction-file`, `skill`, `mcp-server`, `subagent`. `NotApplicable`
for `hook` — a hook's effect is a `decision`/`fault` question, not a behaviour-change one in v0.1.

**basis**: **always `claimed`.** Efficacy is measured by ablation against a live model and is
stochastic by construction; the schema enforces `basis: "claimed"` for this attribute and rejects
`re-derivable` outright. A `claimed` efficacy row is never proof and MUST be read as author-reported
(see README, `basis`).

**inputHash**: not required — `basis`, not `inputHash`, is what makes a row re-derivable, and a
verifier MUST NOT recompute this row regardless of whether one is present. A producer MAY still
carry an `inputHash` over `(model, date, nPerArm, scenario set)` for provenance or deduplication
(e.g. to skip re-running an ablation whose exact inputs were already measured). `conditions` is
what MUST bind the claim to the specific run it came from, with or without an `inputHash`.

**Two models, not one.** An efficacy row can name up to two different models, and they play
different roles. The **subject model** (`conditions.model`) is the model under test: it runs both
arms — once with the rule prepended to the task prompt, once without — and its behaviour is what
the row reports on. The **judge model** (`conditions.judgeModel`) never performs a task; it only
reads a recorded transcript afterwards and decides whether that arm met the rule's criterion. The
two are recorded separately because they answer different questions: swapping the subject model
asks "does this rule change behaviour on a *different* model"; swapping the judge model only
changes how strictly compliance is graded. A fair comparison across subject models — the reason a
manifest names several `models` at once — holds the judge fixed: one `judgeModel` grading every
arm is what makes the resulting lifts comparable to each other at all.

**`judge: "deterministic"` vs `judge: "model"`.** A rule whose criterion is machine-checkable is
graded by code, never by a model, and `conditions.judge` records `"deterministic"` for that grading
path regardless of whether a `judgeModel` happens to be configured. `conditions.judge` is
`"model"` only once at least one rule in this row was actually graded by the configured judge. A
rule with a prose-only criterion and no judge model configured is never guessed at: its id is
listed in `values.ungraded` and it contributes nothing to the row's pooled lift. This is what keeps
a `claimed` row honest about *how* each piece of it was graded, not just that it was.

**The ablation.** v0.1 names its ablation `prompt-prefix-v1` (`conditions.ablation`): the rule's own
text is prepended to the task prompt for the "with" arm and omitted for the "without" arm —
nothing more. This is a prompt-level ablation, not an installed-plugin one: it never loads the
plugin, registers a hook, or calls an MCP tool. A `prompt-prefix-v1` result says "this rule's
*text*, placed in front of the model, changes its behaviour"; it says nothing about whether the
artifact's actual packaging (a hook, a tool description) delivers that text faithfully in a real
install — `reachability` and `conformance` are the rows that speak to that. A reader who sees a
`PASSED` `efficacy` row and assumes the plugin itself was installed and exercised has misread it.

**Transcripts.** Every arm's raw output is recorded once, before any grading happens, so grading is
a separate and repeatable step from running the model. The statement's `byproducts` MUST list the
recorded transcripts as a `resourceDescriptor` with `mediaType:
"application/vnd.context-report.transcripts+json"`, bound by digest — never inlined, since a run
can record many transcripts. A verifier or a later re-grading step reads the same transcripts
rather than re-running the subject model.

**Ingested vendor results.** A plugin author who has already run Anthropic's
`claude plugin eval --ablation with-without` need not re-run anything: context-report ingests that
tool's own `aggregate-result.json` and turns it into this same row shape. `conditions.ablation` is
then `"claude-plugin-eval@<schemaVersion>"` — `<schemaVersion>` is the vendor result's own
`schemaVersion` field — meaning the arms were run by the vendor's tool in its own sandbox with the
plugin actually installed, a real client install unlike `prompt-prefix-v1` above; context-report
only parsed the result and never re-executed the subject model. `conditions.judge` is
`"vendor-grader"` for such a row: grading was done by the vendor tool's own graders (deterministic
checks and its `llm` grader), not by a judge context-report configured, and `conditions.judgeModel`
is `null` because the vendor result never names the model behind that `llm` grader. `values.vendor`
(present only on an ingested row) is `{tool, schemaVersion, suite, cases, skippedGraderTypes}`:
`tool` names the vendor tool; `schemaVersion` and `suite` are copied from the result; `cases` is the
case count; `skippedGraderTypes` lists any grader `type` string outside the reference's known set
(`regex`, `tool_used`, `tool_order`, `file_exists`, `llm`, `baseline`) — its `passed` field was still
used, this is informational only.

**Shape**: `conditions` — `{ablation, model, judgeModel, judge, measuredOn, nPerArm}`: `ablation`
is the ablation design name (`"prompt-prefix-v1"` in v0.1, or `"claude-plugin-eval@<schemaVersion>"`
for an ingested vendor result, see above); `model` is the exact subject model string under test;
`judgeModel` is the judge's model string, or `null` when no judge model was configured (always
`null` for an ingested vendor result); `judge` is `"deterministic"`, `"model"`, or `"vendor-grader"`
(see above); `measuredOn` is the measurement date; `nPerArm` is the per-arm sample size. `values` —
`{perRule, ungraded, tokensPerArm, unexercised, vendor}`: `perRule` is an array with one entry per
graded rule, each `{ruleId,
lift, liftCI,
adherenceWith, adherenceWithout, observationsPerArm, verdict, confirmed}` (`verdict` is one of
`"keep"`, `"dead-weight"`, `"ineffective"`, `"weak"`; `confirmed` says whether enough observations
exist to act on that verdict — a verdict without `confirmed` is a hint, not a recommendation);
`ungraded` is the rule ids no judge could grade, never silently dropped; `unexercised` (optional)
is the rule ids the subject carries that no task exercised — a fact about the task set, reported so
a reader knows which rules the estimate says nothing about; `tokensPerArm` (optional) is
`{with: {inputTokens, outputTokens}, without: {inputTokens, outputTokens}}`, present only when the
run recorded token usage — never a price, only counts a catalog can price however it likes;
`vendor` (optional, see "Ingested vendor results" above) is present only on a row built from an
ingested vendor result. `estimate` — `pointEstimate`,
`confidenceInterval` (`confidenceLevel`, `lowerBound`, `upperBound`), and `standardError` after
Criterion.rs/CycloneDX, computed over the pooled lift across every graded rule. No `measurement`.

**result semantics**: `PASSED` — the pooled lift's 95% Newcombe interval excludes zero and its
width does not exceed the point estimate. `WARNED` — the interval excludes zero but is wide
relative to the point estimate (width greater than the lift itself): a real effect, not yet pinned
down tightly. `FAILED` — the interval's lower bound is at or below zero: no effect distinguishable
from the control arm in the declared direction. `NotAvailable` — nothing could be graded: every
rule with a prose criterion had no judge model to grade it against, and none of the subject's rules
had a machine-checkable criterion either; `reasoning` states how many paired transcripts were still
recorded, so a `NotAvailable` row is not a dead end — the raw material to grade later is right
there under `byproducts`. None of these is a claim the artifact is "good"; a consumer decides what
lift, at what confidence, clears its own bar.

**since**: v0.1
