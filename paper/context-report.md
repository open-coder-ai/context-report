# Context Report: an attested, re-derivable record of what an agent context artifact does

Status: **skeleton — numbers pending** (2026-09-05). This document is the structure and argument of
a measurement paper; every number it needs is a double-bracketed placeholder such as `[[N plugins]]`
until the producer described in `plan/context-attestation.md` runs and lands results under
`measurements/`.
See `paper/README.md` for how the sections map to the workers producing those numbers.

*What we measured, and what we are willing to say before we measure the rest.* open-coder-ai ·
September 2026.

## Abstract

Every agent-plugin catalog ships bundles with no attached evidence: not that they work, not what
they cost, not how they fail when something goes wrong. The catalogs say so about themselves. The
official Model Context Protocol registry states plainly that it "does not certify that the code is
secure, the tool descriptions are honest, the requested permissions are appropriate, or the runtime
behavior will remain unchanged" [1]. A survey of what vendor catalogs currently require from a
submitting author found that namespace ownership, a schema-validating CLI, and "basic automated
review" are the strongest requirements anywhere in the landscape, and that none of them amount to
machine-readable evidence about behavior, cost, or fault handling [7]. Inside one project that tries
harder than most, the gap has a name: chock's own posture renderer prints `"documented by the
vendor; not witnessed by chock"` for every plugin its manual evidence ledger has not covered [2], and
a later audit of that same project's enforcement ledger found the identical failure one layer down —
a security control whose claimed severity the code could not produce, and eight ledger rows naming
no checkable mechanism at all [3].

This paper describes `context-report`: an in-toto-style attestation format, versioned at
`https://open-coder-ai.github.io/context-report/attestation/v0.1`, that a context-artifact author
produces in their own CI and a vendor catalog verifies at submission. Each row states one measured
fact about one (artifact digest, target agent) pair and carries an explicit `basis` —
`re-derivable`, meaning a verifier can recompute the row from the recorded inputs and a mismatch is
a rejected submission, or `claimed`, meaning the row is stochastic or environment-bound and must be
displayed as an author-reported claim, never as proof. The format states facts; it does not render a
pass/fail verdict for the artifact as a whole, and an unmeasured row is never allowed to read as a
pass.

We report, once measurement lands: dogfood results against `[[N plugins]]` drawn from chock's own
four-agent bundles; a fault-oracle comparison against `[[X% fail open on timeout]]` of the
vendor-documented failure postures this paper cites, re-derived rather than assumed; a
`[[median Y ms per tool call]]` added-latency figure for an installed guard hook, measured as a
distribution rather than a mean; and a `[[mean context tokens added per artifact]]` figure from a
named tokenizer approximation. Every numeric claim above is a placeholder. Every other claim in this
document — the problem, the format, the method, and the threats to trusting either — is written to
stand without them, so that landing the numbers is the only work left.

## 1. Introduction

### 1.1 The problem, in the words of the people who would consume the fix

Coding-agent catalogs are large, growing, and unverified. The official MCP registry's own
disclaimer is unambiguous: it "does not certify that the code is secure, the tool descriptions are
honest, the requested permissions are appropriate, or the runtime behavior will remain unchanged"
[1]. That is not a gap in the registry's ambition; it is an accurate description of what a namespace
listing can check. A 2026 arXiv paper on protocol-level gaps in MCP names the same absence directly,
calling it the "absence of capability attestation" [28] — this paper's subject is one candidate
answer to that named gap, not a claim that no one had noticed it. A survey of what vendors currently
require from a submitting author found that the strongest requirement anywhere in the landscape —
across the official MCP registry, the Anthropic plugin directory, the Cursor Marketplace, OpenAI's
review, and GitHub Copilot's marketplaces — is namespace ownership plus a schema-validating CLI and
"basic automated review," and that none of it amounts to machine-readable evidence about behavior,
cost, or fault handling [7].

The gap is visible inside a project that already tries to be honest about it. chock's
`plugin/posture.py` renders the literal string `"documented by the vendor; not witnessed by
chock"` for any plugin its own manual evidence ledger has not covered — which is to say, for most
of them [2]. The string is not a bug; it is chock being more candid than its competitors. The
purpose of the format this paper describes is to turn that string into a witnessed ledger row,
produced automatically rather than by hand.

Candor about a gap is not the same as closing it, and the same project's own enforcement ledger
shows the failure mode this paper's method is built to avoid. An audit of chock's enforcement matrix
against its code found that of nineteen checkable rows, eighteen could emit the severity they
claimed and one — a security-tier row — structurally could not: every finding it could produce was
downgraded to a severity that cannot fail a build, while the ledger's own text described it as a
blocking control [3]. The same audit found eight ledger rows, roughly a quarter of the security
section, naming no function at all, and two dispatch paths that made the matrix's claims
unverifiable by the very people relying on them until the audit read both by hand. The pattern is
not "the control is missing." It is worse and quieter: a claim on record, a mechanism that exists,
and no way to tell from the ledger alone whether the two still agree. This paper calls that pattern
**claim-outrunning-implementation**, following [3]'s own language, and treats it as the central risk
a self-produced report must be designed against, not merely warned about.

### 1.2 A reachability failure, found live

The same week, a second instance of the pattern surfaced by accident rather than by audit. This
repository's own hook-based gate is registered in three agent adapters by a path relative to the
invoking shell's working directory — `python3 .sdlc/hooks/gate.py claude_code`, and the equivalent
for Cursor and Copilot — rather than by an absolute path anchored to the project root [4]. The
registration works exactly as long as the agent's shell happens to sit at the repository root. A
single `cd` into a subdirectory to read an unrelated source file was enough to break it: every
subsequent tool call in that session failed with `python3: can't open file
'.../adherence/.sdlc/hooks/gate.py'`, and because Claude Code treats a hook error as blocking, the
session lost its shell outright and could not repair itself, since hook configuration is snapshotted
at session start [4].

On the client this was witnessed on, the failure mode is disruptive rather than dangerous — the
gate stops everything, loudly, rather than nothing, quietly. But the same discovery record is
explicit that the inference does not carry over: this repository's own enforcement matrix records
Copilot as fail-open, and if an unresolvable hook script produces the same outcome there as a hook
that runs and returns `allow`, then the identical `cd` silently disables every gate the repository
has on that client, including its history-rewrite protection — a claim the record states plainly it
has *not* tested against a real Copilot client [4]. A first attempt at a fix made the pattern worse
in miniature: editing the generated `.claude/settings.json` file by hand fixed one of three agent
dialects, desynchronized the generator from its output, and was caught only because a separate
drift-checking build step failed and forced a second pass at the fix [4]. Nothing about this
incident required an adversary. It is the motivating anecdote for `reachability` as a first-class,
re-derivable row: the defect is deterministic, cheap to check from a handful of candidate working
directories, and today checked by nobody [4][7].

### 1.3 What this paper is

`context-report` is the format that generalizes both observations into a checkable structure: rows
that state what was measured, from where, against which target agent, and whether the measurement
can be redone by someone who is not the author. This paper is a measurement paper about that format
— the empirical follow-on to two predecessor papers from the same project. *Governed by Assertion*
argues that agent-governance claims decay because no arrow in the claim chain from intent to
conformity is checked against the layer below it, and proposes grading the mechanism rather than the
requirement [5]. *The Enforcement Gap* measures, across a 13-agent survey, that a present-looking
control can fail to reach the agent at all — a matcher for the wrong tool name, an interpreter that
silently resolves to nothing, a fail posture nobody stated — and proposes a witness test that
requires evidence the control fired, not merely that it was configured [6]. This paper narrows both
arguments to one artifact class — plugins, instruction files, skills, hooks, MCP servers, and
subagent definitions collectively termed *agent context artifacts* — and asks the same question in a
form a vendor catalog can act on at submission time: for this specific bundle, on this specific
target agent, what is re-derivable, what is only claimed, and what was never measured at all.

## 2. Background and related work

The landscape below is organized around the ten closest projects found in a roughly 60-search,
60-fetch sweep across web search, GitHub, and the arXiv index, conducted 2026-09-05 before this
format was named [7]. The sweep's verdict was that no project combines an author-side, signed,
per-target-agent report covering reachability, decision replay, fault behavior, cost, interference
and efficacy with a per-row basis field, consumed by a catalog that sets its own thresholds — and
that three specific rows are covered by nobody at all: hook reachability from an arbitrary working
directory, interference between co-installed artifacts, and a `re-derivable`/`claimed` distinction
attached per row rather than to a report as a whole [7].

**NVIDIA SkillEvaluator and Verified Skills.** The closest single project by overlap. A
SkillSpector scan feeds a skill card and an OpenSSF Model Signing signature (`skill.oms.sig`),
covering schema conformance, security, efficacy measured with-versus-without a lift technique, and
efficiency, across Claude Code and Codex [10]. What it lacks is everything this paper's rows add
beyond efficacy and conformance: no hooks, no reachability, no decision replay, no fault-handling
row, and no interference row. More fundamentally, NVIDIA signs the *content* of its own skills, not
the *result* of running someone else's — the rows are not per-target-agent statements about an
arbitrary third-party artifact [10].

**Glama's Tool Definition Quality Score (TDQS).** An open, reimplementable methodology
(`glama-ai/tool-definition-quality-score`) scoring tool descriptions with a tiered A–F grade and a
public API [9]. Its most useful idea, adopted here nearly verbatim, is an `inputHash` on every score:
a hash of the exact inputs, so re-scoring can be skipped when nothing has changed, and — for this
paper's purposes — so a `re-derivable` claim is checkable rather than asserted [9]. TDQS itself
covers tool descriptions only, uses a single LLM-judged stage, and is catalog-run rather than
author-attested.

**OpenAI's plugin submission contract.** Both the ChatGPT and Codex surfaces replay exactly five
positive and three negative test cases per submission, and require every MCP tool to carry
`readOnlyHint` and `destructiveHint` annotations *with a justification*, rejecting submissions where
the annotation does not match observed behavior [11]. This is the closest existing analogue to the
`decision` row's shape, and this format adopts it outright: declared positive and negative cases,
replayed per target agent [11]. What OpenAI's process lacks is attestation and re-derivability — the
review is human-run, once, by the vendor, and produces no artifact a third party could recompute.

**mcpscore.** Marketed as "Lighthouse for MCP": 105 deterministic rules, a `rule_id`-keyed JSON
output, a badge, and a `--fail-under` threshold flag already shipping in a live tool [12]. Its
vendor-sets-the-threshold posture is exactly this format's own division of labor between producer
and catalog, but its scope is MCP protocol conformance only — it does not touch cost, fault
behavior, or cross-plugin interference.

**Docker MCP Catalog and Stacklok ToolHive.** SLSA provenance, an SBOM, and Sigstore signing on
container images, verified by the catalog at ingestion, with tiered admission criteria; ToolHive
stores a `Provenance{PredicateType, Predicate, SignerIdentity, RunnerEnvironment}` record per image
[13]. This is the strongest existing precedent for signed, catalog-verified evidence in this space —
and it attests the *build*, not the *behavior*. ToolHive's own criteria state explicitly that they
carry no performance or testing requirement [13]. `context-report` is offered as the complementary
layer: what SLSA/ToolHive do for "was this artifact built the way its provenance says," this format
does for "does this artifact do what its author says, on this agent, at this cost."

**in-toto Test Result, SLSA Verification Summary Attestation, and SCAI.** The attestation plumbing
itself, and the source of most of this format's field names, detailed in Section 3. in-toto Test
Result supplies the `PASSED | WARNED | FAILED` result enum and a `configuration[]` array [14]. SLSA
Provenance v1 supplies `producer`/`metadata`/`resolvedDependencies`/`byproducts`, renaming `builder`
to `producer` because a report's producer plays the same trust-determining role SLSA assigns to a
build's builder [16]. SCAI v0.3 supplies the per-row shape itself —
`attributes[]{attribute, target, conditions, evidence}` — under the heading "evidence-based
assertions about software artifact attributes or behavior," widened here so `evidence` is an array
rather than SCAI's single descriptor [15]. None of the three carries a verdict, a confidence
interval, a measurement distribution, and a derivability flag together, which is why none of them
could be adopted whole [8].

**What no one covers.** Three rows, present in this format's v0.1 attribute registry, appear in
none of the ten closest projects: **hook reachability from an arbitrary working directory** —
reported today only as client bug trackers (`anthropics/claude-code` issues on
`${CLAUDE_PLUGIN_ROOT}` injection on Stop hooks [23]), never tested by any tool; **interference
between co-installed artifacts** — studied only at the paper level, in SkillReact's composition
analysis [25] and "Benign in Isolation, Harmful in Composition" [26], with `cc-plugin-eval`'s
cross-plugin conflict detection still unshipped roadmap [7]; and **a `basis` field carried per row**,
whose nearest analogues are a static-versus-Docker-verified split in one static-analysis tool and
FlowGuard's "signals versus evidence" distinction [27], neither of which attaches the concept to an
individual attestation row the way this format does [7].

## 3. The format

### 3.1 Re-derivability: the one idea the rest of the format serves

A report produced by the party being judged is, by default, the same failure this project has
already found twice in its own work: a claim nobody checks decays regardless of who wrote it, the
enforcement-matrix audit's finding restated as a general rule [3]. The correction is not a promise
of honesty; it is a structural property. Every row in a `context-report` predicate carries a
`basis` field with exactly two values.

| `basis` | Meaning | How a verifier is required to treat it |
| :--- | :--- | :--- |
| `re-derivable` | Deterministic; a verifier can recompute the row cheaply from the subject plus the recorded `configuration[]` and `resolvedDependencies[]`. | A **cache** of a computation the vendor may spot-check. A mismatch is grounds to reject the submission. |
| `claimed` | Stochastic or environment-bound; cannot be recomputed cheaply, or at all, from recorded inputs alone. | A **labeled claim**, bound to a model, a date, and a sample size, displayed as author-reported. Never treated as proof. |

A `re-derivable` row must carry an `inputHash` — a SHA-256 over its exact inputs, borrowed verbatim
from Glama TDQS [9] — which is what makes the word checkable rather than merely asserted. `efficacy`
is the one row the schema forbids from ever being `re-derivable`: it is stochastic by construction,
so the constraint is enforced in the schema itself rather than left to a producer's discretion
(`spec/attestation/v0.1/schema.json`, the `attribute` definition's conditional rules).

One refinement the standards review forced, and left open rather than resolved by convention: a
`re-derivable` measurement is not always identical on re-derivation. Reachability re-derives to the
*same value* on any hardware. Latency re-derives to a *comparable distribution*, not the same
number, because it depends on the runner. The schema marks this with an `environmentSensitive`
boolean plus a recorded `environment` object, rather than inventing a third `basis` value, but the
review states plainly that this is an open decision the spec must settle deliberately, not one this
paper resolves [8].

### 3.2 One statement per (digest, target)

A statement matches SCAI's single-`target` model: it is issued for exactly one artifact digest
against exactly one target agent [15]. A plugin attested for four agents is four statements, not one
statement with four rows of results, because a plugin's fault behavior, and sometimes its
conformance, differ per agent — the same script that fails closed under one harness fails open under
another, discussed below.

### 3.3 The row catalogue

Each row is `(attribute, target, basis, result, evidence)`. A row applies or does not depending on
the subject's `subjectKind` — `decision` and `fault` have nothing to execute against an
`instruction-file`, and the format is required to say `NotApplicable` for such a row rather than
emit an empty pass.

| `attribute` | Question | `basis` | Applies to |
| :--- | :--- | :--- | :--- |
| `conformance` | Does the bundle validate against the target agent's plugin schema? | re-derivable | all kinds |
| `reachability` | Is the artifact registered where the target agent actually reads it, and does it resolve from any working directory? | re-derivable | all kinds |
| `decision` | Given declared positive and negative cases, does the guard allow or deny as stated? | re-derivable | `hook` |
| `fault.scriptMissing` / `fault.interpreterMissing` / `fault.timeout` / `fault.malformedOutput` | What does the target harness do when the guard cannot run correctly? | re-derivable | `hook`, `mcp-server` |
| `cost.latency_ms` | Wall-clock time added per tool call. | re-derivable, environment-sensitive | `hook`, `mcp-server` |
| `cost.context_tokens` | Tokens the artifact adds to the context window at session start. | re-derivable | most kinds |
| `interference` | Does the artifact shadow or contradict another installed artifact? | re-derivable | most kinds |
| `efficacy` | Does the artifact change what the agent does? | claimed, always | most kinds |

### 3.4 The vendor emits two things, not one

A vendor catalog that verifies a report is asked to produce two separate artifacts, never one
blended verdict. The first is a **recomputation**: a second instance of this same predicate, with
`producer.id` identifying the vendor rather than the author, limited to rows whose `basis` is
`re-derivable`, so a consumer can diff author-claimed against vendor-recomputed row by row. The
second is a **verdict** — an in-toto Verification Summary Attestation or the simpler SVR v0.2 that
the VSA specification itself points toward [17] — whose policy references point by digest at both
the author's report and the vendor's recomputation. A recomputation is not a verdict and must not be
shaped like one; this is chock's own "never from evidence" rule made structural, applied to a report
instead of to a repository [30].

### 3.5 Borrowed field names, and where each came from

Nearly every field name in the schema was read from a settled specification rather than invented.
The exceptions are `basis` itself and the `values` / `measurement` / `estimate` result containers.

| Construct | Borrowed from |
| :--- | :--- |
| Envelope, `subject[]`, `ResourceDescriptor{name, uri, digest, mediaType, annotations}` | in-toto Statement/v1 [14] |
| Per-row shape `attributes[]{attribute, target, conditions, evidence}`, top-level `producer` | SCAI v0.3, with `evidence` widened to an array [15] |
| `result: PASSED \| WARNED \| FAILED`, `configuration[]` | in-toto Test Result v0.1 [14] |
| `result: NotAvailable \| Error \| NotApplicable` | OpenSSF Scorecard probe `Outcome`, so an unmeasured row can never read as a pass [21] |
| `producer.id`/`version`, `metadata{invocationId, startedOn, finishedOn}`, `resolvedDependencies[]`, `byproducts[]` | SLSA Provenance v1, `builder` renamed `producer` [16] |
| `reasoning`, `confidenceInterval{lowerBound, upperBound}` | CycloneDX 1.6 declarations and model-card performance metrics [18] |
| `estimate{pointEstimate, standardError, confidenceInterval{confidenceLevel}}` | Criterion.rs `Estimate`, camelCased [19] |
| `measurement{unit, n, percentiles, min, max, mean, stddev}` | JMH `scorePercentiles` and `scoreUnit` — names only, JMH is GPLv2 [20] |
| `inputHash` on every row | Glama TDQS [9] |
| **`basis`**, `values`/`measurement`/`estimate` result containers | New. No precedent found anywhere in the sweep [7][8] |

### 3.6 What was rejected, and why

**SARIF was rejected as the primary format.** GitHub Code Scanning already accepts SARIF from any
producer — the exact "format wins, not a vendor" model this project wants — but SARIF is
location-centric (a bundle-level property has no `physicalLocation`), truncates results by severity,
and has no numeric constructs of its own: every distribution and confidence interval this format
needs would live in an untyped `properties` bag. An in-toto project issue rejected wrapping SARIF for
the same reasons, calling it "GUI-oriented and huge" [22]. A SARIF projection of failing rows,
generated *from* a report so failures surface in a Security tab, remains an option; authoring
directly in SARIF does not.

**SLSA's Verification Summary Attestation was rejected as the vendor's output shape.** Its
`verifiedLevels` field "SHOULD be one of" the `SLSA_BUILD_LEVEL_0`–`3` constants; custom values are
permitted but must not start with `SLSA_`. A vendor verdict fits the VSA shape — `policy.uri`,
`inputAttestations[]`, `verificationResult`, a custom `verifiedLevels` entry — but strains it, since
the procedure it describes is built around SLSA build tracks, not arbitrary vendor policy. The VSA
specification itself points toward SVR v0.2 as "a simpler verification results predicate" for
exactly this case, and nothing in the standards review forces a choice between the two [17].

### 3.7 Worked example

The schema's own worked example, from `spec/attestation/v0.1/examples/plugin-copilot.json`,
abbreviated:

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    {"name": "my-plugin", "uri": "pkg:generic/acme/my-plugin@1.4.0",
     "digest": {"sha256": "3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855e"}}
  ],
  "predicateType": "https://open-coder-ai.github.io/context-report/attestation/v0.1",
  "predicate": {
    "subjectKind": "plugin",
    "target": {"name": "copilot", "annotations": {"clientVersion": "1.104"}},
    "producer": {
      "id": "https://github.com/acme/my-plugin/.github/workflows/context-report.yml@refs/tags/v1.4.0",
      "version": {"context-report": "0.1.0"}
    },
    "metadata": {"invocationId": "...", "startedOn": "2026-09-05T10:00:00Z",
                 "finishedOn": "2026-09-05T10:12:00Z"},
    "configuration": [ ... ],
    "resolvedDependencies": [ ... ],
    "attributes": [
      {"attribute": "reachability", "basis": "re-derivable", "result": "PASSED",
       "inputHash": "sha256:cc0c4429...", "conditions": {"cwdTested": ["/", "/src", "/src/deep"]},
       "evidence": [{"name": "reachability.log", "digest": {"sha256": "dd0c4429..."}}]},
      {"attribute": "fault.timeout", "basis": "re-derivable", "result": "PASSED",
       "inputHash": "sha256:ff0c4429...", "values": {"failMode": "fail-open"},
       "reasoning": "Copilot documents timeouts as always fail-open; measured behaviour matched the documentation."},
      {"attribute": "cost.latency_ms", "basis": "re-derivable", "result": "PASSED",
       "inputHash": "sha256:110c4429...", "environmentSensitive": true,
       "environment": {"runner": "ubuntu-24.04", "cpu": "x86_64"},
       "measurement": {"unit": "ms", "n": 200, "percentiles": {"50": 143, "95": 210, "99": 380},
                        "min": 98, "max": 512, "mean": 151, "stddev": 44}},
      ...
      {"attribute": "efficacy", "basis": "claimed", "result": "PASSED",
       "conditions": {"ablation": "with-vs-without", "model": "example-model-2026-08",
                       "measuredOn": "2026-09-05", "nPerArm": 35},
       "estimate": {"pointEstimate": 0.31, "standardError": 0.066,
                     "confidenceInterval": {"confidenceLevel": 0.95, "lowerBound": 0.18, "upperBound": 0.44}}}
    ],
    "byproducts": [ ... ]
  }
}
```

The `fault.timeout` row above is the shape §4 calls a documented-oracle row: its `result` is
measured, but its `reasoning` states explicitly that the measurement matched a documented vendor
posture rather than standing alone.

## 4. Method

This section states, for each row family, how v0.1 intends to produce it. `context-report`'s
repository presently carries a schema, one worked example, and their tests — no reference producer
or verifier exists yet, a fact stated in the repository's own README rather than inferred here.
Everything below is therefore a plan for the producer, not a report of one running, and every detail
this paper could not read directly from a source is marked.

**Reachability.** The producer installs the artifact using each target agent's own documented
registration mechanism, then invokes a tool call from a small set of candidate working directories
and checks whether the artifact's hook or configuration resolves in each. The worked example tests
three candidate directories (`/`, `/src`, `/src/deep`) (§3.7).
`[[confirm with W3/W4: canonical cwd set tested per target agent]]`

**Decision replay.** For `hook` subjects, the producer replays the declared positive and negative
cases from OpenAI's submission-contract shape [11] against the guard script under each target
agent's real invocation path, and records `PASSED`/`FAILED` per case rather than a single aggregate.

**Fault handling.** The producer forces four conditions against a `hook` or `mcp-server` subject —
the script missing, the interpreter absent, an artificial timeout, and malformed output from the
guard, the last modeled directly on a marketplace audit finding a `PreToolUse` guard that fails open
on malformed JSON via an unconditional `sys.exit(0)` on parse error, rated Critical in that audit
[7] — and records the target agent's real behavior against each. Vendor fault semantics contradict
each other by design, which is the entire reason this row exists: Claude Code proceeds past a
non-zero exit other than 2 and discards output on timeout; GitHub Copilot is fail-closed on a
crashing `preToolUse` command hook but "timeouts are always fail-open, including for admin-deployed
policy hooks," and a hook that times out is not killed, so a later deny can be discarded [24];
Cursor's `failClosed` defaults to `false`; Codex CLI's posture is unconfirmed in the sources this
paper draws on, blocked by inaccessible documentation [7]. v0.1's schema requires a `reasoning`
string on any row whose `result` is `NotAvailable`, `Error`, or `NotApplicable`, so that a row the
producer could not measure against a real client states, in that field, that it is instead citing
this documented oracle rather than a witnessed run — the format's schema enforces the
*distinction*, not which value was used for that run. **v0.1 does not drive a live client**, per the
repository's own status; where this paper's method describes comparing measured behavior to the
documented oracle, the "measured behavior" side of that comparison is future work, not something
this paper can report today.
`[[confirm with W3/W4: which fault rows need a live client vs. oracle-only, and the sandboxing approach]]`

**Cost — latency.** The producer times `n` tool-call invocations with the artifact installed, using
a monotonic clock, and reports the distribution — `unit`, `n`, `percentiles`, `min`, `max`, `mean`,
`stddev` — rather than a single mean, following JMH's percentile-map convention adopted into the
schema [20]. The row is marked `environmentSensitive`, and the `environment` object records enough
about the runner (at minimum, per the worked example, the runner image and CPU architecture) that a
vendor compares like with like rather than treating a re-derived distribution as a byte-for-byte
match (candidate mechanism: Python's `perf_counter`, referenced in the plan only as something
chock's own source does not currently use).
`[[confirm with W3/W4: timing mechanism, n, and environment fields recorded]]`

**Cost — context tokens.** The producer estimates the tokens an artifact adds to a session's context
window at start, using a named tokenizer approximation rather than a model provider's exact
tokenizer, since the format is meant to work across target agents whose underlying models and exact
tokenizers are not uniformly known to the producer. This is the same order of cost the literature
already documents at the session level — one industry figure cited in the prior-art sweep puts a
seven-server session at 67,300 tokens before the first user message, and a peer-reviewed estimate
puts per-turn MCP overhead at 10,000–60,000 tokens [29] — which this row is designed to attribute
back to the single artifact responsible, rather than leave as an undifferentiated session total.
`[[confirm with W3/W4: tokenizer approximation used and its disclosed error bound]]`

**Interference.** For an artifact declared alongside other installed artifacts, the producer checks
for shadowed or contradicting rules, extending chock's existing ambient-rule conflict check from
instruction files to hooks and skills [30]. Where no co-installed artifacts are declared for a run,
the row is `NotAvailable` with a `reasoning` string saying so, matching the worked example (§3.7).

**Efficacy.** The only `claimed` row, by schema constraint. Measured by paired ablation — with the
artifact present against a control run without it — bound to a specific `model`, `date`, and
`nPerArm`, and reported as an `estimate` with a confidence interval rather than a bare point value,
following Criterion.rs's shape [19]. This is the row the plan explicitly assigns to a separate
product, `adherence`, rather than to this format's own producer [30]; the numbers this paper
eventually reports for `efficacy` are therefore expected to come from that project's measurements,
not from `context-report`'s own harness.

**The honesty rules that bind every row above.** An unmeasured row is never rendered as a pass: the
schema requires `NotAvailable`, `Error`, and `NotApplicable` results to carry a `reasoning` string,
and forbids `efficacy` from ever claiming `re-derivable`. A `re-derivable` row without an
`inputHash` is rejected by the schema outright, which is the mechanism, not merely the policy, that
keeps the word checkable (`spec/attestation/v0.1/schema.json`; `tests/test_schema.py` in this
repository already asserts both rules).

## 5. Results

*To be filled from `measurements/` once the producers land. Every row below is a placeholder; no
number in this section has been measured.*

### 5.1 Dogfood: chock's own bundles

| Artifact | Target agent | `conformance` | `reachability` | `fault.timeout` | `cost.latency_ms` (p50/p95) | `cost.context_tokens` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `[[artifact one]]` | `[[target agent]]` | `[[result]]` | `[[result]]` | `[[result]]` | `[[latency p50]]` / `[[latency p95]]` | `[[mean tokens]]` |
| `[[artifact two]]` | `[[target agent]]` | `[[result]]` | `[[result]]` | `[[result]]` | `[[latency p50]]` / `[[latency p95]]` | `[[mean tokens]]` |

`[[N dogfood bundles measured]]` bundles across `[[N target agents]]` target agents.

### 5.2 Top-N catalog plugins

| Rank | Plugin | Catalog | `reachability` | `fault` (worst-case oracle match) | `cost.latency_ms` p50 | `interference` |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `[[plugin name]]` | `[[catalog name]]` | `[[result]]` | `[[result]]` | `[[latency p50]]` | `[[result]]` |
| 2 | `[[plugin name]]` | `[[catalog name]]` | `[[result]]` | `[[result]]` | `[[latency p50]]` | `[[result]]` |

Sampled from `[[N catalog plugins]]` across `[[catalog list]]`, selection method
`[[sampling method]]`.

### 5.3 The fault oracle versus documentation

| Target agent | Failure kind | Documented posture | Measured posture | Match? |
| :--- | :--- | :--- | :--- | :--- |
| Claude Code | timeout | proceeds, output discarded | `[[measured posture]]` | `[[match or mismatch]]` |
| GitHub Copilot | `preToolUse` crash | fail-closed | `[[measured posture]]` | `[[match or mismatch]]` |
| GitHub Copilot | timeout | fail-open (documented as always) | `[[measured posture]]` | `[[match or mismatch]]` |
| Cursor | script error, `failClosed` unset | fail-open (default) | `[[measured posture]]` | `[[match or mismatch]]` |
| Codex CLI | any | unconfirmed in sources | `[[measured posture]]` | `[[match or mismatch]]` |

`[[X% fail open on timeout]]` of the fault rows measured against the documented oracle in this
table.

## 6. Threats to validity

**Latency is environment-sensitive.** `cost.latency_ms` re-derives to a comparable distribution,
not an identical number, because it depends on the runner's hardware and load. The schema's
`environmentSensitive` marker and recorded `environment` object are the format's answer, but the
open question the standards review left unresolved — whether this deserves a third `basis` value
rather than a marker on `re-derivable` — is unsettled, and any threshold a vendor sets on a latency
row inherits that uncertainty [8].

**Tokenizer approximation versus a model's real tokenizer.** `cost.context_tokens` is estimated
with a named approximation rather than each target agent's exact tokenizer, because the producer
cannot always know which model a given agent session is running. The size of the resulting error,
and whether it is disclosed per row, is unresolved in this draft — see the method-section
placeholder above.

**Documented versus measured, for fault rows.** Where v0.1 does not drive a live client, a
`fault.*` row's `reasoning` can only state that it matches a documented vendor posture, not that it
was witnessed. A documented posture can itself be stale — vendor fail-posture behavior has already
been observed to change within the same survey window in this project's own prior work [6] — and a
row citing documentation rather than a live run should be read with that in mind until a producer
exists that drives a real client.

**The runner is untrusted unless builder identity is verified.** A `context-report` predicate is
only as credible as the identity of whoever produced it. The format's own standards review states
this as a hard requirement, not a preference: a report is credible when its attestation carries the
*workflow's* identity via SLSA-style builder identity fields, so a vendor can require "produced by
the official action on a hosted runner" rather than accept hand-written JSON [8]. Any result in this
paper produced by a runner whose identity a reader cannot verify should be treated the same way this
paper treats a `claimed` row: labeled, not proof.

**Coverage of the landscape sweep.** The background in Section 2 rests on a single sweep of
roughly 60 searches and fetches across web, GitHub, and the arXiv index, conducted 2026-09-05, using
an alternate fetch path where the network environment's egress policy blocked the origin directly
[7]. Several sources are marked snippet-only in that sweep's own working notes, and this paper
repeats that qualification rather than upgrading a snippet-only claim to a confirmed one. A sweep
using different search terms, or run after this date, could surface a closer prior-art candidate
than the ten catalogued here.

## 7. Discussion

**What a catalog can do with a report.** Nothing in this format tells a vendor what to accept. A
`cost.latency_ms` row states a number; Copilot may decide 143 ms is acceptable for a given class of
hook while a stricter catalog rejects the same number for the same class. That division of labor —
the format states facts, the vendor sets thresholds — is deliberate, stated in the plan this paper
follows, and is the same posture SkillEvaluator's tier semantics already take: deterministic gates
that a catalog may choose to block on, and advisory measurements a catalog may choose to ignore
[30][7].

**Why a format, not a tool.** The reference producer that will eventually emit these reports is
explicitly not the product; the predicate type is. This mirrors why SARIF outlived any one static
analyzer and why SBOM formats outlived every individual generator that shipped before them: a format
a vendor's existing verifier already knows how to check (`gh attestation verify --predicate-type
<ours>` needs no new infrastructure to run) is a request a vendor can grant without adopting a third
party's pipeline, where "adopt our test suite" is a request no vendor has granted to date [30].

**Limits, stated plainly.** This format attests behavior an author's CI could observe; it does not
attest intent, and a re-derivable row proves only that the reported number matches what a verifier's
own recomputation produces, not that the number is good. Interference is scoped to co-installed
artifacts declared to the producer, not every artifact a user might actually have installed.
Efficacy is, by the schema's own rule, never more than a labeled claim. None of this is a defect
particular to `context-report`; it is the same boundary every attestation format accepts by choosing
to state facts rather than adjudicate them, restated here because a paper that argues for honest
claims should not quietly exempt its own subject.

## 8. Conclusion

Agent context artifacts ship today with no evidence attached to any of the questions that matter
before installing one: does it reach the agent it claims to support, does it fail the way its
author believes it does, what does it cost on every tool call, and does it do anything at all.
Every vendor catalog surveyed says, in one form or another, that it does not check. This paper
describes a format built to close that gap without asking any vendor to adopt anyone else's test
suite: a signed, per-target-agent report whose rows state what was measured and whether the
measurement can be redone by someone other than the artifact's author. The format is finished enough
to validate against; what remains is running it, and reporting, honestly, what comes back.
