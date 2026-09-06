# Governance

context-report is a solo-maintainer project. This document says plainly how it is
run, who decides what, and what happens if the maintainer disappears.

## Decision making

The maintainer ([@open-coder-ai](https://github.com/open-coder-ai)) has final say on
scope, releases, and merges — the common single-maintainer model. In practice,
decisions follow the project's published invariants rather than taste:

- A row's `basis` must match what was actually measured: `re-derivable` only for
  what is recomputed from the subject plus its recorded configuration and hashed
  via `inputHash`; anything else is `claimed`.
- An unmeasured row says `NotAvailable`, `Error`, or `NotApplicable` **and why** — it
  is never reported as a pass.
- Every change lands as a pull request with required CI, including the maintainer's
  own — branch protection applies to everyone.

Disagree with a decision? Open an issue or a Discussion; decisions are explained,
and reversals happen when the argument is better than the invariant it challenges.

## Roles and responsibilities

- **Maintainer**: reviews and merges PRs, triages issues, cuts releases, and holds
  the security-report inbox.
- **Contributors**: anyone via pull request. Requirements are in
  [CONTRIBUTING.md](CONTRIBUTING.md) (DCO sign-off, tests for behavior changes,
  green CI). Sustained, high-quality contributors may be offered triage or commit
  rights; that decision is the maintainer's and will be recorded here when it
  first happens.
- **Security reporters**: see [SECURITY.md](SECURITY.md) — private advisories,
  acknowledged within 7 days, credited unless they prefer otherwise.

## Access continuity

Single-maintainer projects owe their users an answer to "what if you vanish":

- The repository lives under the **open-coder-ai GitHub organization**, not a
  personal account, so ownership can be extended or transferred without rewriting
  history or URLs.
- Everything needed to maintain the project is in the repository itself: the
  schema, the tests, the CI workflows, and the documentation. There is no private
  infrastructure.
- **Commitment**: if the project is visibly unmaintained (no maintainer activity for
  six months) and someone credible wants to continue it, the maintainer intends to
  add maintainers or transfer stewardship rather than let it rot. Forks are also a
  legitimate continuity path — the Apache-2.0 license permits it.

## Changing this document

Like everything else: by pull request. Material governance changes are called out in
release notes.
