# Attribute registry — context-report v0.1

One section per `attribute` value in [`schema.json`](schema.json)'s `$defs.attributeName` enum.
This file is the registry the schema enum is a fingerprint of: a name here without a matching
schema entry, or a schema entry without a matching section, is a bug caught by
`tests/test_spec_prose.py`. `subjectKind` applicability uses the table in
[`../../../plan/context-attestation.md`](../../../../plan/context-attestation.md) (Subject
section) — reproduced per attribute below. A `subjectKind` for which an attribute does not apply
MUST get a row with `result: "NotApplicable"` and `reasoning` naming the kind, never a silently
omitted row and never a `PASSED` standing in for "nothing to check".

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

**Shape**: `conditions.cwdTested` (an array of the working directories exercised, e.g.
`["/", "/src", "/src/deep"]`); `evidence` pointing at a reachability log. No `measurement`/
`estimate`.

**result semantics**: `PASSED` — resolves from every tested `cwd`. `FAILED` — fails to resolve
from at least one tested `cwd`; `values` or `reasoning` SHOULD name which. `NotApplicable` never
applies here in v0.1.

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

**Shape**: `values.failMode`: `"fail-open"` or `"fail-closed"`.

**result semantics**: `PASSED` means "measured; see `values.failMode`", never a judgment call.

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

**basis**: `re-derivable`, and `environmentSensitive: true` SHOULD be set: the measurement
procedure is deterministic, but the millisecond values it produces depend on the runner (see
README's "Re-derivable is not identical"). `environment` (e.g. `{runner, cpu}`) SHOULD be recorded
so a verifier compares a re-run's distribution to this one rather than expecting the same numbers.

**inputHash MUST cover**: the subject digest, `target` and its `clientVersion`, and the number and
shape of the sampled tool calls (`measurement.n`).

**Shape**: `measurement` — `unit: "ms"`, `n` (sample count), `percentiles` (at least `"50"`,
`"95"`, `"99"`), `min`, `max`, `mean`, `stddev`. No `values`/`estimate`.

**result semantics**: `PASSED` means "measured; see `measurement`" — a distribution is not
inherently a pass or fail; a consumer applies its own latency budget. `Error` — the measurement
run itself failed to complete (e.g. the harness crashed mid-sampling), with `reasoning`.

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

**Shape**: `conditions` — `{ablation, model, measuredOn, nPerArm}` at minimum (an ablation design
name, the exact model string, the measurement date, and the per-arm sample size); `estimate` —
`pointEstimate`, `confidenceInterval` (`confidenceLevel`, `lowerBound`, `upperBound`), and
`standardError` after Criterion.rs/CycloneDX. No `measurement`/`values`.

**result semantics**: `PASSED` — the ablation found a statistically meaningful effect in the
declared direction; `reasoning` SHOULD note the ablation design if non-obvious. `WARNED` — an
effect was found but the interval is wide relative to the point estimate. `FAILED` — no
distinguishable effect from the control arm. None of these is a claim the artifact is "good"; a
consumer decides what lift, at what confidence, clears its own bar.

**since**: v0.1
