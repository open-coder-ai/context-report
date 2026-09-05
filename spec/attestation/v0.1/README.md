# context-report attestation v0.1

This is the normative specification for the `context-report` predicate. The JSON Schema at
[`schema.json`](schema.json) is authoritative; this document explains what its fields mean and
what a producer or verifier MUST, SHOULD, or MAY do with them. Where the two disagree, the schema
wins and this file has a bug.

The key words "MUST", "MUST NOT", "SHOULD", "SHOULD NOT", and "MAY" are to be interpreted as in
RFC 2119, following the convention of the SLSA and in-toto specifications this predicate borrows
from.

## Purpose

A `context-report` statement records measured facts about one agent context artifact — a plugin,
an `AGENTS.md` or other instruction file, a skill, a hook, an MCP server, or a subagent definition
— **as observed by one target agent**. Two harnesses can disagree about the same artifact: a hook
that fails closed on a crash under one client and fails open under another is not a detail, it is
the security-relevant fact the report exists to carry. A statement therefore covers exactly one
`(subject digest, target)` pair, and its rows are facts, never a verdict: the predicate MUST NOT
assert that the artifact as a whole "passes" or "fails". A consumer (a plugin catalog, a registry,
a reviewer) sets its own thresholds over the rows it cares about; the format's job ends at stating
the fact accurately and saying how it was obtained.

## Envelope

A `context-report` statement is an [in-toto Statement/v1](https://github.com/in-toto/attestation)
whose `predicateType` is `https://open-coder-ai.github.io/context-report/attestation/v0.1` and
whose `predicate` conforms to [`schema.json`](schema.json). Producers MUST emit exactly one
statement per `(subject digest, target)` pair — an artifact attested for four agents is four
statements against the one subject digest, never a single statement with four targets.

Per in-toto Statement/v1, subjects are matched **purely by digest**: `subject[]` entries carry a
`digest` (this predicate's schema requires it via `resourceDescriptor`), and a `name` or `uri`
alone never binds a statement to an artifact. Consumers MUST ignore fields they do not recognize —
this is what lets `attributes[].values`, `.conditions`, and `.environment` stay producer-defined
free-form objects without breaking older verifiers.

**Signing.** A producer SHOULD emit the statement via [`actions/attest`](
https://github.com/actions/attest), which wraps it in a DSSE envelope inside a Sigstore bundle,
signs it with the CI workflow's OIDC identity via Fulcio, and records it in the public Rekor log.
This is why the format asks nothing of the author's laptop: the trust a consumer places in a row
comes from `predicate.producer.id` (see below) carrying the *workflow's* identity, not a claim
typed by a human.

**Verification.** A consumer verifies with `gh attestation verify <artifact> --predicate-type
https://open-coder-ai.github.io/context-report/attestation/v0.1`, optionally narrowed with
`--signer-workflow <owner>/<repo>/<path>@<ref>` and `--deny-self-hosted-runners` to require "the
official action, on a hosted runner" rather than merely "some signature exists". A verifier MUST
reject a statement whose `predicateType` does not match exactly — `0.X` is part of the identity
(see Versioning).

## Predicate fields

`predicate` is required to carry `subjectKind`, `target`, `producer`, and `attributes`;
`metadata`, `configuration`, `resolvedDependencies`, and `byproducts` are optional.

- **`subjectKind`** — one of `plugin`, `instruction-file`, `skill`, `hook`, `mcp-server`,
  `subagent`. Says what kind of context artifact the subject is; a row applies to a `subjectKind`
  or it does not (see [attributes.md](attributes.md) for the table). New in this predicate — no
  format surveyed during the standards review carried a subject taxonomy for agent context
  artifacts.
- **`target`** — the agent this statement is about. `target.name` (required) is a short agent
  identifier (`"copilot"`, `"claude-code"`, `"cursor"`); `target.uri` MAY link to the agent's own
  identity; `target.annotations.clientVersion` SHOULD be set whenever a `fault.*` row is present,
  because fail-open/fail-closed behaviour is a property of a client *version*, not of the agent
  name in general (open question, see Versioning). Modeled on SCAI's single-`target` per
  assertion, which keeps `gh attestation verify` queries to one statement per agent rather than an
  array a verifier must filter.
- **`producer`** — who ran the checks. `producer.id` (required, a URI) is, verbatim from SLSA
  Provenance's `builder.id`, "the sole determiner of" how much trust a consumer places in the
  rows: the reference producer sets it to the CI workflow's own identity (e.g.
  `https://github.com/<org>/<repo>/.github/workflows/context-report.yml@refs/tags/v1.4.0`).
  `producer.version` is a map of tool name to version (e.g. `{"context-report": "0.1.0"}`).
- **`metadata`** — `invocationId`, `startedOn`, `finishedOn` (RFC 3339 UTC, borrowed verbatim from
  SLSA Provenance). Timestamps MUST end in `Z`.
- **`configuration`** and **`resolvedDependencies`** — arrays of `resourceDescriptor` (SLSA
  Provenance names, unchanged). Together with `attributes[].inputHash`, these are what makes a
  `re-derivable` row recomputable rather than merely asserted (see Rows below): `configuration`
  records the exact config a run used (e.g. `context-report.config.json` by digest);
  `resolvedDependencies` records the exact versions of everything that could change the outcome
  (e.g. the `context-report` library itself, by digest).
- **`attributes`** — the rows; see Rows below. MUST contain at least one entry.
- **`byproducts`** — optional supporting artifacts a verifier or reader MAY want (e.g. a full
  replay trace), by `resourceDescriptor`. Not required for recomputation; `evidence` on individual
  rows is for that.

A `resourceDescriptor` (in-toto Statement/v1, unchanged) carries `name`, `uri`, `digest`,
`content` (base64), `downloadLocation`, `mediaType`, `annotations`, and MUST carry at least one of
`uri`, `digest`, or `content`.

## Rows

Each entry in `attributes[]` is one row: one attribute, measured for the one target the statement
covers. A row is `{attribute, basis, result, ...}`; `attribute`, `basis`, and `result` are always
required. Its shape follows SCAI's attribute-assertion model, with `evidence` widened from SCAI's
single descriptor to an array — the one deliberate deviation from that source.

### `basis`

Every row declares whether a verifier can check it or must trust it:

- **`re-derivable`** — deterministic; a verifier can recompute the row from the subject plus the
  recorded `configuration[]` and `resolvedDependencies[]`. A `re-derivable` row MUST carry an
  `inputHash`: a `sha256:`-prefixed hex digest (Glama TDQS's convention) over the exact inputs the
  row was computed from. The convention is fixed so a third-party verifier can recompute it: the
  digest is SHA-256 of the canonical JSON (keys sorted, separators `,` and `:`, non-JSON values
  stringified) of the array `[subject sha256, target.name, target.annotations.clientVersion or
  null, attribute, ...row inputs]`, where the row inputs for each attribute are listed under
  "inputHash MUST cover" in [attributes.md](attributes.md). The three leading elements bind the row
  to this subject and this target; two statements about different bundles can never share a hash.
  `inputHash` is what turns "re-derivable" into a checkable claim instead of an assertion of
  intent: a verifier that reruns the check and gets a matching `inputHash` has *cached* the row; a
  verifier that reruns it and gets a different result has caught a rejected submission.
- **`claimed`** — stochastic or otherwise not cheaply recomputable; author-reported. A `claimed`
  row MAY carry an `inputHash` for provenance or deduplication. Its presence does not make the
  row re-derivable; only `basis` does, and a verifier MUST NOT recompute a `claimed` row
  regardless. A consumer MUST NOT treat a `claimed` row as proof of anything: it is a labeled
  claim, bound to the model and date under which it was produced (recorded in `conditions`, see
  `efficacy` in [attributes.md](attributes.md)), to be displayed as author-reported and never
  merged into a trust decision the way a matched `re-derivable` recomputation can be. `efficacy`
  MUST always be `claimed` — it is stochastic by construction and the schema enforces this.

### `result`

`result` is one of `PASSED`, `WARNED`, `FAILED` (in-toto Test Result v0.1, unchanged) or
`NotAvailable`, `Error`, `NotApplicable` (OpenSSF Scorecard probe outcomes). A row whose `result`
is `NotAvailable`, `Error`, or `NotApplicable` MUST carry `reasoning` explaining why the row could
not be measured, and such a row **MUST NOT be read as a pass**. This is in-toto's monotonic
principle applied to a single row: a policy consuming this predicate should prefer "deny unless a
passing, matched row exists" over "deny only if a failing row exists", precisely because an
unmeasured row is silent, not clean. What `PASSED`/`WARNED`/`FAILED` mean is attribute-specific —
for several attributes (notably `fault.*`) `PASSED` means only "measured; see the recorded value",
never a value judgment about which value is good. See [attributes.md](attributes.md) for the
per-attribute rule.

### Other row fields

- **`environmentSensitive`** / **`environment`** — marks a re-derivable row whose values depend on
  the runner; see "Re-derivable is not identical" below. MUST be `true`, with `environment`
  recorded, on a measured `cost.latency_ms` row; the schema enforces this.
- **`conditions`** — a free-form object recording what was held fixed for this measurement (e.g.
  `efficacy`'s `{ablation, model, measuredOn, nPerArm}`, or `reachability`'s
  `{cwdTested: [...]}`). Producer-defined; consumers MUST ignore keys they do not recognize.
- **`values`** — a free-form object for a row's non-distributional result (e.g. `fault.*`'s
  `{failMode: "fail-open" | "fail-closed"}`).
- **`measurement`** — a measured distribution, after JMH `scorePercentiles`: `unit` and `n`
  (required), plus `percentiles` (a map keyed by percentile, e.g. `"50"`, `"95"`, `"99"`), `min`,
  `max`, `mean`, `stddev`.
- **`estimate`** — a point estimate with its interval, after Criterion.rs `Estimate` and
  CycloneDX's `confidenceInterval`: `pointEstimate` and `confidenceInterval` (required — itself
  `{confidenceLevel, lowerBound, upperBound}`), plus optional `standardError`.
- **`evidence`** — an array of `resourceDescriptor` pointing at supporting artifacts for this
  specific row (e.g. a log file), by digest.
- **`reasoning`** — free text; required whenever `result` is unmeasured (above), and SHOULD be
  present whenever a row's value needs a sentence of context (CycloneDX's `reasoning`, unchanged).

## Re-derivable is not identical

**Decided in v0.1.** Some `re-derivable` rows recompute to the exact same value on any runner:
`reachability`'s "does this cwd resolve the hook" is a yes/no fact of the bundle and the agent,
independent of hardware; `cost.context_tokens` under a named tokenizer is one number. Others
recompute to a *comparable distribution*, not the same number: `cost.latency_ms` measured on a
laptop and on a CI runner differ in absolute value while describing the same behaviour. v0.1 keeps
two `basis` values and marks the second case on the row: `environmentSensitive: true` with
`environment` recorded (at least the platform and CPU count, so a verifier compares like with
like). The schema requires both on a measured `cost.latency_ms` row. A verifier recomputing a row
compares the full `measurement` exactly unless the row is `environmentSensitive`, in which case it
compares `unit` and that both sides have `n >= 1`, and leaves the numbers to the consumer's own
threshold. A third `basis` value was considered and rejected: the procedure is re-derivable; only
the numbers are not, and that is a property of the row, not of the trust model.

## Applicability by `subjectKind`

Not every attribute applies to every kind: a prose `instruction-file` has nothing to execute, a
`hook` script's own text is not injected into the context window. Each section of
[attributes.md](attributes.md) states its "Applies to" list, and the schema enforces the same table
at the predicate level: for a `(subjectKind, attribute)` pair the registry excludes, the row MUST be
present with `result: "NotApplicable"` and a `reasoning`, never omitted and never `PASSED`. The
table is also shipped as data with the reference producer (`applicability-v0.1.json`) so a producer
emits those rows without reading the prose.

## What the verifier emits

A verifier that recomputes rows emits two separate statements, never one:

1. **A recomputation** — a second `context-report` statement against the same subject digest and
   target, with `producer.id` set to the verifier, and `attributes[]` limited to the rows the
   verifier is able to recompute (`basis: "re-derivable"` only). A consumer diffs the author's
   report against this recomputation row by row: matching `inputHash` values and matching
   `result`s mean the submission is corroborated; a mismatch on any row is a rejected submission.
   A recomputation carries no verdict field and MUST NOT be shaped like one — it is exactly this
   predicate, run again by a second producer.
2. **A verdict** — a separate statement, in an *unrelated* predicate (an in-toto SVR v0.2 verdict,
   or a VSA using non-`SLSA_`-prefixed custom levels), whose policy inputs point by digest at both
   the author's report and the recomputation above.

The two are kept apart because a recomputation is an input to a decision, never the decision
itself — mixing them would let a producer's own report re-encode a "pass" through the back door
that Purpose above rules out, and would leave a consumer no way to tell "the vendor observed the
same facts" apart from "the vendor approved this artifact".

## Versioning

Per in-toto convention, `0.X` versions are **major**: fields MAY be added, removed, or change
meaning between `0.1` and `0.2` without notice, and the major is carried in the `predicateType` URI
itself (`.../attestation/v0.1`, not a version field inside the body). A verifier pinning
`--predicate-type` to a specific URI is therefore pinning to a specific schema, by construction.
Consumers MUST ignore predicate fields they do not recognize (see Envelope), which is what allows
additive changes within a major to stay compatible in practice even though the version number does
not promise it.

Each attribute definition in [attributes.md](attributes.md) carries its own `since: vX.Y` line,
independent of the predicate's own version and independent of any producer tool's version. This is
deliberate: OpenSSF Scorecard versions only the tool that runs its checks, not each check
individually, so a check's behaviour can change silently under a stable-looking tool version. This
predicate does not copy that — an attribute's meaning is pinned by the spec, not by whichever
`context-report` library version happened to compute the row.

## Extensions

An attribute name outside the v0.1 registry MUST match `^x-[a-z0-9][a-z0-9._-]*$` (e.g.
`x-license-check`). Extension rows follow every other rule in this document — `basis`, `result`,
and the `inputHash`/`reasoning` requirements apply identically. A consumer that does not recognize
an `x-` attribute MUST ignore the row rather than reject the statement.

## Non-goals

- **Not SARIF.** SARIF is location-centric (built around `physicalLocation`), truncates results by
  severity, and has no numeric constructs for a distribution or a confidence interval — every row
  here would end up in an untyped `properties` bag. in-toto issue #268 rejected wrapping SARIF for
  the same reasons. A producer MAY project failing rows into SARIF for a code-scanning UI; it MUST
  NOT be the format it authors in.
- **Not a VSA.** SLSA's Verification Summary Attestation is about SLSA build levels
  (`verifiedLevels` SHOULD be one of `SLSA_BUILD_LEVEL_0..3`); a vendor verdict over this
  predicate's rows fits an SVR-shaped predicate (or a VSA with non-`SLSA_` custom levels) better
  than it fits this one. See What the verifier emits above.
- **Not protocol conformance.** JSON-RPC framing and MCP capability negotiation belong to
  `modelcontextprotocol/conformance`; this predicate is a complementary layer about behaviour, not
  protocol shape.
- **Not authorship provenance.** Who signed the statement is Sigstore's job (the DSSE envelope and
  Fulcio certificate), not a predicate field.
- **Never a pass/fail for the artifact as a whole.** Restated from Purpose because it is the one
  rule every other section exists to protect: this predicate states facts: it never renders a
  verdict, and a consumer that reads an entire statement as "passed" has misread it.
