# Context Report: an attested, re-derivable record of what an agent context artifact does

Status: **draft with dogfood and catalog-sample numbers** (2026-09-06). Section 5 reports the first
run of the reference producer over chock's own bundles and a sample of eighteen public Claude Code
plugins (`paper/measurements/catalog-sample/`). The statements belong with the artifact they measure and will be
published in `open-coder-ai/chock-catalog` under `measurements/context-report/` once this format is
public; until then they are held on that repository's PR #57, and will be regenerated against the
published producer before they land. The live-client side of the fault oracle (§5.3) has not been
run and says so.
See `paper/README.md` for how to regenerate the results.

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

We report a first dogfood run of the reference producer over 88 bundles built from chock's 22
policies for four target agents. Sixteen bundles carry a hook. With the plugin-root variable the
client sets, every hook resolves from all four working directories tested; without it, none does for
three of the four agents, while the Copilot bundle exits 0 by design and so reads as reachable. All
sixteen hooks exit 0 with no deny on stdout when fed malformed input, which the adapter's own source
describes as a deliberate choice. Per-invocation latency of a guard hook, measured as a distribution
with a realistic pre-tool payload, has a median p50 between 42 and 47 ms per target agent on the
build machine, of which about 13 ms is the interpreter starting. The median bundle adds an estimated
222 tokens of context under a named, deterministic approximation. A sample of eighteen public Claude
Code plugins, chosen by a rule fixed before measuring, found three plugins whose hook script ships
without its execute bit and so never runs, two whose hooks shell out through `npx` at roughly 670 ms
per tool call against 6 to 52 ms for local scripts, a hundredfold spread in context weight, and every
running hook allowing on malformed input. Measuring it also surfaced four producer gaps, each fixed
before the committed run. The live-client side of the fault oracle was not measured: v0.1 does not
drive a client, and the rows say so rather than pass.

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

This section states, for each row family, how the v0.1 reference producer (`context-report
produce`) measures it and what it declines to measure. The repository carries the schema, a worked
example, the producer, and a verifier (`context-report verify`) that recomputes the re-derivable rows
and emits an in-toto verification summary. Every row the producer cannot measure is emitted with a
`reasoning` string; nothing below is inferred from the schema alone.

**Reachability.** The producer runs the hook command exactly as registered from four working
directories — the artifact root, a nested directory inside it (an existing one, or a temporary one
created and removed), the parent, and a temporary directory outside the tree — feeding a realistic
pre-tool payload for the target agent, and records per directory whether the command ran and the
first line of its standard error. The environment variables the run was given (for example the
client's plugin-root variable) are recorded on the row, because the dogfood showed reachability is a
property of the variable, not of the script. The worked example's three directories (§3.7) are
superseded by this set.

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
*distinction*, not which value was used for that run. **v0.1 does not drive a live client.** Of the four
conditions, one is measured without a client: `fault.malformedOutput` runs the hook against three
malformed stdin cases (unparseable JSON, empty input, a null tool input) plus a benign well-formed
control, and records the exit code and any decision word found in stdout JSON, since the hook-JSON
protocols carry the deny in stdout and not in the exit code. The other three — `fault.scriptMissing`,
`fault.interpreterMissing`, `fault.timeout` — are emitted as `NotAvailable`, and their `reasoning`
quotes the documented vendor posture with its basis (`vendor-docs, NOT measured`). The hook runs as
an ordinary subprocess through the shell in the artifact directory with a per-run scoped environment
and a timeout; there is no filesystem or network isolation, which §6 lists as a threat. Before every
producer runs, the producer digests the subject, and after they finish it digests it again; a
mismatch refuses the statement, so a hook that writes into its own bundle cannot produce a report
bound to the wrong bytes.

**Cost — latency.** The producer times `n` tool-call invocations with the artifact installed, using
a monotonic clock, and reports the distribution — `unit`, `n`, `percentiles`, `min`, `max`, `mean`,
`stddev` — rather than a single mean, following JMH's percentile-map convention adopted into the
schema [20]. The row is marked `environmentSensitive`, and the `environment` object records enough
about the runner (at minimum, per the worked example, the runner image and CPU architecture) that a
vendor compares like with like rather than treating a re-derived distribution as a byte-for-byte
match The producer times each `subprocess.run` of the registered command with Python's `perf_counter`,
wall-clock, with the payload on stdin; `n` defaults to 50 and is recorded in the row's `conditions`
along with `warmup_excluded: false`. The `environment` object records the platform string, the
Python version, the CPU count, and the variables the run was given. A run that times out aborts the
measurement, and a measurement in which no run exits 0 is emitted as `Error` with the numbers kept
for inspection: a benign payload should be allowed, so those runs timed the failure path, not the
hook. The first dogfood produced a confident 16 ms "latency" for a hook whose script could not be
found before this rule existed. (That run was on a busier machine; the committed run's floor is
13 ms.)

**Cost — context tokens.** The producer estimates the tokens an artifact adds to a session's context
window at start, using a named tokenizer approximation rather than a model provider's exact
tokenizer, since the format is meant to work across target agents whose underlying models and exact
tokenizers are not uniformly known to the producer. This is the same order of cost the literature
already documents at the session level — one industry figure cited in the prior-art sweep puts a
seven-server session at 67,300 tokens before the first user message, and a peer-reviewed estimate
puts per-turn MCP overhead at 10,000–60,000 tokens [29] — which this row is designed to attribute
back to the single artifact responsible, rather than leave as an undifferentiated session total. The approximation is named
`approx-regex-v1`: each maximal run of word characters is one token and each remaining
non-whitespace character is one token, summed over the files the target agent injects at session
start for the artifact's kind (skill and instruction files, a plugin's manifest, a subagent's
definition). It is deterministic, so the row re-derives exactly. Its error against any provider's
tokenizer has not been measured; the row's `conditions.method` names the approximation so a reader
can discount it, and §6 lists the missing bound.

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

The numbers below were produced by the reference producer on
2026-09-05 with `n = 20` latency samples per hook bundle, on a four-CPU Linux build machine. Every
statement validates against the v0.1 schema and is bound to the digest of the bundle it measured.
The statements, the inventory and the script that produced them belong with the artifacts and are
held for `open-coder-ai/chock-catalog` (`measurements/context-report/`, PR #57) until this format is
public, to be regenerated against the published producer before they land: the format's own
repository carries no measurement of any particular product, which is the arrangement the format asks
of every author, and a public catalog should not carry a report in a format nobody can yet read.

### 5.1 Dogfood: chock's own bundles

chock builds each of its 22 policies into a plugin bundle for four target agents, 88 bundles in all.
Four policies carry a pre-tool hook (`block-destructive-commands`, `block-no-verify`,
`protect-agent-config`, `protect-commit-privacy`), so 16 bundles have something to execute. Each hook
bundle was measured twice: with the plugin-root variable the client would set (`resolved`) and
without it (`unresolved`).

| Target agent | Bundles | With hook | Reachable, resolved | Reachable, unresolved | Exit 0 and no deny on malformed stdin | Latency p50 / p95 ms, median over hook bundles | Context tokens, median per bundle |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Claude Code | 22 | 4 | 4 of 4 | 0 of 4 | 4 of 4 | 46.6 / 51.7 | 222 |
| Codex CLI | 22 | 4 | 4 of 4 | 0 of 4 | 4 of 4 | 44.5 / 46.6 | 222 |
| GitHub Copilot | 22 | 4 | 4 of 4 | 4 of 4 | 4 of 4 | 42.0 / 43.4 | 222 |
| Cursor | 22 | 4 | 4 of 4 | 0 of 4 | 4 of 4 | 43.7 / 45.9 | 222 |

Three findings, stated as the rows state them.

*Reachability is a property of the client's variable, not the script.* Each bundle's registered
command resolves its script through the client's plugin-root variable (`CLAUDE_PLUGIN_ROOT`,
`PLUGIN_ROOT`, `CURSOR_PLUGIN_ROOT`). With the variable set, every hook ran from all four working
directories. Without it, none ran for three agents — the interpreter reported it could not open
`/scripts/<agent>.py`, and the latency row for those runs is `Error`, not a number. The Copilot
bundle reads as reachable in both conditions because its command is written to exit 0 when the
variable is unset, by chock's design; the row records that exit, and a consumer that wants to
distinguish "ran the guard" from "exited quietly" has the benign control case in
`fault.malformedOutput` to compare against.

*Every hook exits 0 with no deny on malformed input.* Fed unparseable JSON, empty stdin, or a null
tool input, all 16 hooks exit 0 and write nothing to stdout, so under each agent's protocol the tool
call proceeds. This is not an accident the format caught: the adapter that chock generates, from the
agentseam runtime template, comments the branch "malformed input is not the agent's fault to pay
for: allow, stay silent." The row states the fact and the design rationale sits in the adapter; which
of the two a catalog acts on is the catalog's threshold, which is the division of labor §7 argues for.

*Latency is a distribution with a knowable floor.* Per invocation with a realistic pre-tool payload,
the median hook bundle has a p50 between 42.0 and 46.6 ms depending on the target's adapter, and
the median p95 per target is within 5 ms of its p50; single bundles reach 58 and 61 ms at p95. The `Error` rows from the unresolved condition, which time
the interpreter starting and failing to open a file, sit at 13 ms; that is the floor a Python
hook pays before any policy code runs. The rows are `environmentSensitive`, and the environment
object on each records the platform, Python version, and CPU count.

The context-token estimate under `approx-regex-v1` is 222 tokens for the median bundle, which
carries one skill file; hook bundles, which add a manifest and a script-bearing hooks file, range
from 288 to 646.

### 5.2 Top-N catalog plugins

Eighteen public Claude Code plugins, measured on 2026-09-06 with `n = 20`, statements and inventory
under `paper/measurements/catalog-sample/`. The selection rule was fixed before any measurement:
from Anthropic's official marketplace (291 plugins at the cloned commit), every plugin declaring a
hook, up to ten, ties broken alphabetically; then the highest-starred hook-bearing plugins from the
two most-starred community marketplaces not owned by Anthropic, to fifteen; then five plugins with no
hooks so the not-applicable rows are exercised. The two community marketplaces, with 95 plugins
between them, contain three hook-bearing plugins in total, so the sample has thirteen hook-bearing
plugins rather than fifteen. That is a finding about the ecosystem, not a shortfall in the search.

| Plugin | Hooks declared | Reachability | Malformed input allows | Latency p50 / p95 ms | Context tokens |
| :--- | :--- | :--- | :--- | :--- | ---: |
| agentforce-adlc | 2 | PASSED, 4 of 4 | yes | 26.8 / 28.7 | 29,625 |
| ai-plugins | 4 | PASSED, 4 of 4 | yes | 32.0 / 37.4 | 2,289 |
| aws-core | 2 | PASSED, 4 of 4 | yes | 45.5 / 51.8 | 57,466 |
| planning-with-files | 6 | PASSED, 4 of 4 | yes | 6.0 / 6.2 | 25,179 |
| protect-mcp | 2 | PASSED, 4 of 4 | yes | 665.8 / 686.5 | 1,845 |
| review-agent-governance | 2 | PASSED, 4 of 4 | yes | 672.0 / 711.2 | 1,634 |
| carta-cap-table | 9 | FAILED, 0 of 4 | never ran | Error: exit 126 | 127,818 |
| carta-crm | 7 | FAILED, 0 of 4 | never ran | Error: exit 126 | 44,588 |
| carta-investors | 8 | FAILED, 0 of 4 | never ran | Error: exit 126 | 146,663 |
| altimate-code, aws-serverless, aws-startup-advisor, azure | 1 each, none pre-tool | NotApplicable | NotApplicable | NotApplicable | 3,940 to 74,359 |
| five plugins declaring no hooks | 0 | NotApplicable | NotApplicable | NotApplicable | 1,509 to 43,647; one has no text |

Four findings, stated as the rows state them.

*Reachable was not the same as executable, and now it is.* Three plugins share a dispatch script
committed without its execute bit. The path resolves, so the first producer reported them reachable
while the latency and fault rows showed the hook never started. Exit 126 now counts as unreachable,
and the three rows agree with each other.

*Hook cost spans two orders of magnitude.* The two plugins whose hook shells out through `npx` cost
about 670 ms per tool call. The four that run a local `python3`, `bash` or `sh` script cost 6 to 52
ms. This is visible only because latency is measured per invocation and reported as a distribution.

*Every hook that runs allows on malformed input.* All six plugins whose pre-tool hook ran exit 0 with
no deny when fed unparseable input, empty input, or a null tool input. The same was true of all
sixteen chock hooks in §5.1. Whether that is acceptable is a catalog's threshold; the format only
records that it is universal in this sample.

*Context weight varies a hundredfold.* From about 1,500 to about 147,000 estimated tokens per plugin
under `approx-regex-v1`, with the largest bundles among the hook-bearing ones. One plugin injects no
text at all, and its row says so rather than reporting zero.

The sample also measured the producer. Its first pass misreported five plugins: two declare their
hooks only through the plugin manifest's `hooks` field, at paths discovery did not read; one runs
`sh` with the script in `args`, which discovery dropped and then, in a first fix, quoted in a way
that stopped the plugin-root variable expanding; three had the execute-bit case above; and one
plugin's Python hook wrote bytecode into its own directory on first run, moving the subject digest
mid-measurement so the producer refused the statement. Each is fixed, each has a test naming the
plugin that found it, and only the third pass is committed. A format whose producer must be checked
against real artifacts before its numbers can be trusted is the point; this is what that looks like.

### 5.3 The fault oracle versus documentation

| Target agent | Failure kind | Documented posture | Measured posture |
| :--- | :--- | :--- | :--- |
| Claude Code | timeout | proceeds, output discarded | not measured: v0.1 does not drive a client |
| GitHub Copilot | `preToolUse` crash | fail-closed | not measured: v0.1 does not drive a client |
| GitHub Copilot | timeout | fail-open (documented as always) | not measured: v0.1 does not drive a client |
| Cursor | script error, `failClosed` unset | fail-open (default) | not measured: v0.1 does not drive a client |
| Codex CLI | any | unconfirmed in sources | not measured: v0.1 does not drive a client |

No row in this table has a measured side. The producer emits `fault.scriptMissing`,
`fault.interpreterMissing`, and `fault.timeout` as `NotAvailable` with the documented posture quoted
in `reasoning` and labelled `vendor-docs, NOT measured`; the schema forces the label, and this table
reproduces it rather than promoting documentation to observation.

## 6. Threats to validity

**Latency is environment-sensitive.** `cost.latency_ms` re-derives to a comparable distribution,
not an identical number, because it depends on the runner's hardware and load. The schema's
`environmentSensitive` marker and recorded `environment` object are the format's answer, and v0.1
settled the question the standards review raised: two `basis` values stay, the marker is required on
a measured latency row, and a verifier compares such a row's distribution shape rather than its
numbers [8]. Any threshold a vendor sets on a latency row still inherits the runner's variance.

**Tokenizer approximation versus a model's real tokenizer.** `cost.context_tokens` is estimated
with a named approximation rather than each target agent's exact tokenizer, because the producer
cannot always know which model a given agent session is running. The approximation is named in the row, so
it re-derives exactly, but its error against a provider tokenizer has not been measured; until it
is, the 222-token figure in §5 is an ordering, not a cost.

**Documented versus measured, for fault rows.** Where v0.1 does not drive a live client, a
`fault.*` row's `reasoning` can only state that it matches a documented vendor posture, not that it
was witnessed. A documented posture can itself be stale — vendor fail-posture behavior has already
been observed to change within the same survey window in this project's own prior work [6] — and a
row citing documentation rather than a live run should be read with that in mind until a producer
exists that drives a real client.

**The dogfood subject is the author's own artifact.** Every bundle in §5 was built by chock and
measured by a producer written alongside it, on one machine, on one day. The findings are stated as
the rows state them and are re-derivable from the committed statements, but nothing in §5 is
evidence that the format's rows discriminate among third-party artifacts. §5.2 is the first such
evidence: eighteen plugins nobody here wrote, with the rows separating hooks that run from hooks
that cannot, and the producer's own gaps found and fixed in the process. It is one target agent,
one machine, one day, and thirteen hook-bearing plugins; it is not the ecosystem.

**The hook runs unsandboxed.** The producer executes the registered command as an ordinary
subprocess with a timeout, in the artifact directory, with only the environment variables it was
given. A hostile hook can read and write what the producer's user can. The digest-before-and-after
guard refuses a statement when the subject changed, and the CLI refuses to write the report inside
the subject, but neither is isolation; a producer run on untrusted artifacts belongs in a container.

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
measurement can be redone by someone other than the artifact's author. The reference producer has
run over the author's own 88 bundles and over eighteen public plugins nobody here wrote, and the
rows it emitted are committed with the digests they bind to. The second run found three shipped
hooks that never start and fixed four gaps in the producer along the way. One measurement comes
next: a producer that drives a live client for the three fault rows v0.1 marks `NotAvailable`
(§5.3), so that the documented postures in that table acquire a measured column.
