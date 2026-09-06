# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x (latest) | yes |
| older | no |

Per in-toto convention, `0.X` versions are major: fields may change until 1.0. Only
the latest `0.1.x` release is supported.

## Reporting a vulnerability

context-report defines a report format an author produces in their own CI and a
catalog verifies at submission; a flaw here can propagate into every consumer that
trusts a statement it produces or verifies.

- **Preferred:** open a private security advisory:
  <https://github.com/open-coder-ai/context-report/security/advisories/new>
- Do **not** open a public issue for exploitable findings.
- Include: affected schema field, tool path, or spec section; reproduction steps;
  and impact (e.g. a `re-derivable` row that is not actually recomputable, a
  verifier accepting a tampered statement, or a `basis` a row cannot back up).

Expect an acknowledgment within 7 days and an initial assessment within 14 days.
Confirmed vulnerabilities are fixed in a patch release and credited to the
reporter unless they prefer otherwise.

## Threat model

The spec's central honesty claim is the `basis` field (`re-derivable` vs.
`claimed`) and the `inputHash` that backs a `re-derivable` row. The two limits
below are properties of the design rather than bugs, and are stated here because a
report format that leaves them implicit is claiming more than it does.

### A statement is only as trustworthy as its verifier

context-report does not itself attest anything; it defines what a producer states
and what a verifier is expected to check. A verifier that skips the `inputHash`
recomputation for `re-derivable` rows, or that treats a `claimed` row as if it
were `re-derivable`, has silently dropped the one distinction the format exists to
make. Nothing in the schema can force a downstream verifier to actually verify.

### `efficacy` rows are `claimed`, by design

The `efficacy` row measures paired-ablation lift via a model call
(`context-report[efficacy]`, `provider: "anthropic"` in v0.1). That measurement is
stochastic and bound to a model and date — it is a labeled claim, never proof, and
is not eligible for `basis: re-derivable`. A verifier that treats it otherwise is
misusing the format, not exploiting a flaw in it.

### This repository is itself a chock adopter

Like the organization's other public repositories, this repository governs its
own contributions with [chock](https://github.com/open-coder-ai/chock)
(`.agents/policies/`). `git commit --no-verify` skips every git hook, and
therefore every compiled gate; the CI-side gate (`chock check`,
`chock sync --repo . --check` in `ci.yml`) is the backstop that neither
`--no-verify` nor an unsynced clone can bypass — see chock's own
[SECURITY.md](https://github.com/open-coder-ai/chock/blob/main/SECURITY.md) for
the full argument.
