# Conventions

The house style. New contributions should follow it; `ruff` enforces what it can, this
document covers what it can't.

## Code

- **One-line docstring** per module, class and function; a comment only where the code is
  genuinely non-obvious. The *why* belongs in the PR body, not the diff.
- **Externalize, don't hardcode.** Artifacts in another language (a shell wrapper, a
  workflow fragment) go in template files under the package's data directory; facts about
  the world (vendor names, field mappings, prompt text) go in JSON the code reads, never in
  branching logic.
- **`__TOKEN__` placeholders**, swapped with `str.replace`, never f-strings — so a template
  file stays valid in its own language as-is and CI can lint it (`actionlint`, `shellcheck`,
  `yaml.safe_load`, whichever applies).
- **Error and diagnostic messages stay in code**, beside the condition that raises them —
  not centralized in a strings file that drifts from what actually raises.
- **Behaviour stays code.** The moment a "config" needs branching it is a program in
  disguise; write the branch in Python instead of teaching a data file to express it.
- **Schema copies are byte-identical to the spec they mirror.** `spec/attestation/v0.1/schema.json`
  is the one copy; anything that embeds or re-derives it (docs, examples, the hosted Pages
  copy) must match byte-for-byte, checked rather than assumed.
- **Never a blanket `ruff --fix`.** `SIM`/`RUF`/`UP` autofixes rewrite code, not just
  formatting; review each rule category on its own against the tests before applying it.

## Rows and claims

- A row's `basis` must match what was actually done to produce it: `re-derivable` only when
  the row is recomputed from the subject plus its recorded configuration and carries an
  `inputHash` over those exact inputs; `claimed` for anything stochastic or author-reported.
- An unmeasured row says `NotAvailable`, `Error`, or `NotApplicable` **and why** — it is
  never silently omitted or reported as a pass.
- Extensions use an `x-` prefix; the base vocabulary (`conformance`, `reachability`,
  `decision`, `fault.*`, `cost.*`, `interference`, `efficacy`) is not extended by adding new
  top-level rows to the schema without a version bump.

## Verifying a change

From the repository root:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

A test failure is fixed in the code, never in the test. A lint finding is fixed at its
cause, never by adding it to `per-file-ignores` without a reason comment next to the
entry explaining why that file is the exception.

## Records and plans

- Nothing under `discovery/` in this repository yet; if that changes, a dated record is
  immutable once committed — supersede it with a newer dated file, never edit one in place.
- A plan document opens with a status line and carries enough context that a session with
  no conversation history can execute it. When a plan and the code disagree, the code is
  right and the plan's status line is wrong.

<!-- agentseam:begin -->
# context-report

Authoritative rules and conventions: `AGENTS.md` (repo root) — read it before any work.
Boundaries: read `README.md` and `docs/` only when the task is to change them.
<!-- agentseam:end -->
