# References

Numbered list backing the `[n]` citations in `paper/context-report.md`. Every entry below appears,
by name or by explicit identifier (arXiv id, GitHub issue, repository slug, or quoted URL), in one
of the source records this paper was drafted from. Where a source gave no public URL for a named
project, that is stated rather than filled in with a guess. All entries accessed 2026-09-05, the day
the source records were read for this draft.

1. **Model Context Protocol registry — self-description disclaimer.** Quoted: "does not certify
   that the code is secure, the tool descriptions are honest, the requested permissions are
   appropriate, or the runtime behavior will remain unchanged." What it is: the official MCP
   registry's own statement about what it does not check. URL: not given in the source record (name
   only). Basis: vendor-docs, quoted in `plan/context-attestation.md`. Accessed 2026-09-05.

2. **chock, `plugin/posture.py`.** Quoted: `"documented by the vendor; not witnessed by chock"`,
   and the `UNWITNESSED` ledger constant it renders from. What it is: a coding-agent plugin
   governance tool's own honesty string for unverified plugins. URL: not given in the source record
   (name only; chock is a sibling project, not a public URL in these records). Basis: repo, read
   from `plan/context-attestation.md`. Accessed 2026-09-05.

3. **Enforcement-matrix audit.** What it is: a discovery record auditing chock's enforcement
   ledger against its own code; source of the SEC-7 finding (a claimed blocking control that cannot
   emit a failing severity) and the "governed by assertion" pattern restated for a claim ledger. URL:
   `discovery/2026-09-04-enforcement-matrix-audit.md` (this organization's internal record; no
   public URL). Basis: repo (first-party audit at a pinned SHA). Accessed 2026-09-05.

4. **Gate-registration cwd-dependence.** What it is: a discovery record documenting a `PreToolUse`
   gate registered by a relative path in three agent adapters, reproducing a session-blocking failure
   on Claude Code and reasoning through the fail-open implication for Copilot. URL:
   `discovery/2026-09-04-gate-registration-cwd-dependence.md` (internal record; no public URL).
   Basis: repo, witnessed on Claude Code, inferred (not tested) for Copilot. Accessed 2026-09-05.

5. **Governed by Assertion.** What it is: this project's first predecessor paper, arguing that
   agent-governance claim chains are unverified at every link and proposing an Enforcement Class
   ladder graded by mechanism rather than requirement. URL:
   `https://claude.ai/code/artifact/44860473-179f-4dd2-8dd7-28a711bd895e` (rendered artifact, per the
   paper's own status line); source file `papers/governed-by-assertion.md`. Basis: paper (this
   project's own, draft status). Accessed 2026-09-05.

6. **The Enforcement Gap.** What it is: this project's second predecessor paper, a 13-agent survey
   finding that present-looking controls (matchers, interpreters, fail postures) can fail to reach
   the agent at all, and proposing a witness-test vocabulary (`enforced` / `enforced-at-commit` /
   `advisory` / `unsupported`). URL:
   `https://claude.ai/code/artifact/33e43e77-0dda-4c8e-af69-4c2a58a0107f` (rendered artifact, per the
   paper's own status line); source file `papers/enforcement-gap.md`. Basis: paper (this project's
   own, review-ready status). Accessed 2026-09-05.

7. **Prior-art sweep.** What it is: the discovery record surveying roughly 60 searches and fetches
   for prior art on context-artifact attestation, naming the ten closest projects, the vendor fault
   semantics table, the submitter-requirements table, and the three uncovered rows. URL:
   `discovery/2026-09-05-context-attestation-prior-art.md` (internal record; no public URL). Basis:
   repo (first-party sweep; several entries within it are marked snippet-only in its own text).
   Accessed 2026-09-05.

8. **Standards review.** What it is: the discovery record analyzing which existing attestation
   standards the predicate borrows field names from, why SARIF and SLSA VSA were rejected as the
   primary format, and the open `environmentSensitive` question for re-derivable measurements. URL:
   `discovery/2026-09-05-context-attestation-standards-review.md` (internal record; no public URL).
   Basis: repo (field names read from canonical specs or protobufs, per the record's own method
   note). Accessed 2026-09-05.

9. **Glama Tool Definition Quality Score (TDQS).** What it is: an open, reimplementable scoring
   methodology for MCP tool descriptions, source of the `inputHash` idea adopted into this format.
   URL: `https://github.com/glama-ai/tool-definition-quality-score` (repository slug given in the
   prior-art sweep). Basis: repo, named in `discovery/2026-09-05-context-attestation-prior-art.md`.
   Accessed 2026-09-05.

10. **NVIDIA SkillEvaluator and Verified Skills.** What it is: a skill-scanning and signing
    pipeline (SkillSpector scan, skill card, `skill.oms.sig` via OpenSSF Model Signing) covering
    conformance, security, and with/without efficacy across Claude Code and Codex. URL: not given in
    the source record (name only). Basis: vendor-source, named in
    `discovery/2026-09-05-context-attestation-prior-art.md`. Accessed 2026-09-05.

11. **OpenAI plugin submission review.** What it is: OpenAI's ChatGPT- and Codex-surface plugin
    review, replaying five positive and three negative test cases per submission and requiring
    justified `readOnlyHint`/`destructiveHint` annotations. URL: not given in the source record (name
    only). Basis: vendor-docs, named in `discovery/2026-09-05-context-attestation-prior-art.md`.
    Accessed 2026-09-05.

12. **mcpscore.** What it is: a deterministic MCP-server scoring tool ("Lighthouse for MCP"), 105
    rules, `rule_id`-keyed JSON output, a `--fail-under` threshold flag. URL: not given in the source
    record (name only). Basis: vendor-source, named in
    `discovery/2026-09-05-context-attestation-prior-art.md`. Accessed 2026-09-05.

13. **Docker MCP Catalog / Stacklok ToolHive.** What it is: catalog and gateway products attesting
    MCP server *builds* via SLSA provenance, SBOM, and Sigstore signing, with a
    `Provenance{PredicateType, Predicate, SignerIdentity, RunnerEnvironment}` record; criteria
    explicitly carry no performance or testing requirement. URL: not given in the source record (name
    only). Basis: vendor-docs, named in `discovery/2026-09-05-context-attestation-prior-art.md`.
    Accessed 2026-09-05.

14. **in-toto Statement/v1 and Test Result v0.1.** What it is: the attestation envelope
    (`_type`, `subject[]`, `ResourceDescriptor`) and the `PASSED | WARNED | FAILED` result vocabulary
    this predicate's envelope and `result` enum are borrowed from verbatim. URL:
    `https://github.com/in-toto/attestation` (linked from this repository's own `README.md`). Basis:
    repo / spec (Apache-2.0), per `discovery/2026-09-05-context-attestation-standards-review.md`.
    Accessed 2026-09-05.

15. **SCAI v0.3 (Supply Chain Attribute Integrity).** What it is: the attribute-assertion spec
    ("evidence-based assertions about software artifact attributes or behavior") this predicate's
    per-row shape (`attributes[]{attribute, target, conditions, evidence}`) and single-target model
    are borrowed from, with `evidence` widened to an array. URL: not given in the source record (name
    only). Basis: spec (Apache-2.0), per
    `discovery/2026-09-05-context-attestation-standards-review.md`. Accessed 2026-09-05.

16. **SLSA Provenance v1.** What it is: the supply-chain provenance spec this predicate's
    `producer`/`metadata`/`resolvedDependencies`/`byproducts` fields are borrowed from, renaming
    `builder` to `producer`. URL: `https://slsa.dev` (named as an egress-blocked host read via a
    mirror, per the standards review's method note). Basis: spec (CSL-1.0 / CC-BY-4.0 text; MIT
    code), per `discovery/2026-09-05-context-attestation-standards-review.md`. Accessed 2026-09-05.

17. **SLSA Verification Summary Attestation (VSA) and SVR v0.2.** What it is: SLSA's vendor-verdict
    predicate, rejected here as the primary vendor-output shape because its `verifiedLevels` values
    are built around SLSA build tracks; the VSA specification itself points to SVR v0.2 as a simpler
    alternative. URL: `https://slsa.dev` (same source domain as [16]). Basis: spec, per
    `discovery/2026-09-05-context-attestation-standards-review.md`. Accessed 2026-09-05.

18. **CycloneDX 1.6.** What it is: the SBOM/declarations spec this predicate's `reasoning` string
    and `confidenceInterval{lowerBound, upperBound}` fields are borrowed from
    (`declarations.claims[]`, `modelCard.quantitativeAnalysis.performanceMetrics[]`). URL:
    `https://cyclonedx.org` (named as an egress-blocked host read via a mirror, per the standards
    review's method note). Basis: spec (Apache-2.0 / ECMA-424), per
    `discovery/2026-09-05-context-attestation-standards-review.md`. Accessed 2026-09-05.

19. **Criterion.rs.** What it is: a Rust benchmarking library whose `Estimate` type
    (`pointEstimate`, `standardError`, `confidenceInterval{confidenceLevel}`) this predicate's
    `estimate` container is borrowed from, camelCased. URL: not given in the source record (name
    only). Basis: repo (Apache-2.0 / MIT), per
    `discovery/2026-09-05-context-attestation-standards-review.md`. Accessed 2026-09-05.

20. **JMH (Java Microbenchmark Harness).** What it is: a JVM benchmarking harness whose
    `scorePercentiles` and `scoreUnit` this predicate's `measurement{unit, n, percentiles, min, max,
    mean, stddev}` container is borrowed from — names only, since JMH is GPLv2. URL: not given in the
    source record (name only). Basis: repo (GPLv2+CPE, names only), per
    `discovery/2026-09-05-context-attestation-standards-review.md`. Accessed 2026-09-05.

21. **OpenSSF Scorecard.** What it is: a supply-chain security scoring tool whose probe `Outcome`
    values this predicate's `NotAvailable | Error | NotApplicable` result extension is borrowed from,
    and whose `publish_results` workflow is cited as the closest existing precedent for
    "author's laptop untrusted, CI runner is not." URL: not given in the source record (name only).
    Basis: repo (Apache-2.0), per `discovery/2026-09-05-context-attestation-standards-review.md`.
    Accessed 2026-09-05.

22. **SARIF (Static Analysis Results Interchange Format) and its rejection.** What it is: the OASIS
    standard for static-analysis results, rejected here as the primary format for being
    location-centric, truncating results by severity, and lacking numeric constructs; an in-toto
    project issue (#268) rejected wrapping SARIF for the same reasons, calling it "GUI-oriented and
    huge." URL: `https://www.oasis-open.org` (named as an egress-blocked host read via a mirror, per
    the standards review's method note). Basis: spec (OASIS, RF-on-RAND), per
    `discovery/2026-09-05-context-attestation-standards-review.md`. Accessed 2026-09-05.

23. **`anthropics/claude-code` issue tracker.** What it is: issues #50960, #3583, and #66557,
    reporting that `${CLAUDE_PLUGIN_ROOT}` is not injected on Stop hooks — the class of reachability
    bug this format's `reachability` row is designed to catch, documented today only as client bug
    reports. URL: `https://github.com/anthropics/claude-code/issues` (repository named in the source
    record; specific issue numbers given, not individually linked). Basis: repo, named in
    `discovery/2026-09-05-context-attestation-prior-art.md`. Accessed 2026-09-05.

24. **`github/copilot-cli` issue #2893.** What it is: a report that Copilot CLI does not kill a
    timed-out hook, so a later deny decision from that hook can be discarded — cited as part of the
    vendor fault-semantics oracle this format's `fault.timeout` row re-derives. URL:
    `https://github.com/github/copilot-cli/issues/2893` (repository and issue number given in the
    source record). Basis: repo, named in
    `discovery/2026-09-05-context-attestation-prior-art.md`. Accessed 2026-09-05.

25. **SkillReact.** What it is: a paper studying interference between co-installed agent skills at
    the paper level only, cited as evidence that the `interference` row's subject has no shipped
    tooling. URL: `https://arxiv.org/abs/2606.00448` (arXiv id given in the source record). Basis:
    paper, named in `discovery/2026-09-05-context-attestation-prior-art.md`. Accessed 2026-09-05.

26. **"Benign in Isolation, Harmful in Composition."** What it is: a paper on compositional harm
    between co-installed agent components, cited alongside SkillReact as paper-level-only coverage of
    interference. URL: `https://arxiv.org/abs/2606.15242` (arXiv id given in the source record).
    Basis: paper, named in `discovery/2026-09-05-context-attestation-prior-art.md`. Accessed
    2026-09-05.

27. **FlowGuard.** What it is: a paper distinguishing "signals" from "evidence," the nearest
    existing analogue to this format's per-row `basis` field, though not attached to an individual
    attestation row. URL: `https://arxiv.org/abs/2607.14754` (arXiv id given in the source record).
    Basis: paper, named in `discovery/2026-09-05-context-attestation-prior-art.md`. Accessed
    2026-09-05.

28. **"Breaking the Protocol."** What it is: a paper naming the "absence of capability attestation"
    as a protocol-level gap in MCP, cited as the motivating framing this format is one candidate
    answer to. URL: `https://arxiv.org/abs/2601.17549` (arXiv id given in the source record). Basis:
    paper, named in `discovery/2026-09-05-context-attestation-prior-art.md`. Accessed 2026-09-05.

29. **"MCP Tax."** What it is: a paper estimating 10,000–60,000 tokens of per-turn MCP protocol
    overhead, cited alongside an industry figure (67,300 tokens before the first user message with
    seven installed servers) as the order of magnitude the `cost.context_tokens` row is designed to
    measure per artifact. URL: `https://arxiv.org/abs/2604.21816` (arXiv id given in the source
    record). Basis: paper, named in `discovery/2026-09-05-context-attestation-prior-art.md`.
    Accessed 2026-09-05.

30. **`plan/context-attestation.md`.** What it is: this project's own plan document — the model
    (attestation, not certification), the basis principle, the v1 row catalogue, the draft predicate,
    and the explicit non-goals (protocol conformance, authorship provenance, any pass/fail verdict)
    this paper describes. URL: `plan/context-attestation.md` (internal record; no public URL). Basis:
    repo (this project's own planning document, status: building as of 2026-09-05). Accessed
    2026-09-05.
