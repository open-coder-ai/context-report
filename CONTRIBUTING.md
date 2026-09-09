# Contributing to context-report

**First off — thank you.** context-report gets better every time someone reports a
confusing error message, fixes a typo, tightens a schema field, or challenges a design
decision. You're in the right place.

## Every contribution counts — not just code

You do **not** need to write Python to make a real difference here:

- **Docs & examples** — clarify a confusing section, add a worked example, fix a typo.
- **Bug reports** — a good reproduction is worth its weight in gold. [Open an issue](https://github.com/open-coder-ai/context-report/issues/new).
- **Spec feedback** — a field name that doesn't match the format it was borrowed from, an
  ambiguous `basis` case, a `NotApplicable` reason that isn't actionable.
- **Ideas & feedback** — start a [Discussion](https://github.com/open-coder-ai/context-report/discussions). Telling us what's confusing *is* a contribution.

## The ladder

Contributions here get larger in one direction, and you can stop at any rung:

1. **An evidence report** — run a probe, paste what actually happened. No code, and it is the
   most useful thing a newcomer can do, because a claim nobody re-ran is just a claim. In this
   repo that rung is not an analogy: an evidence report *is* the product. Run
   `context-report produce --subject <path> --kind plugin --target claude_code --n 20 --out
   report.json` against any public plugin, then `context-report verify report.json --subject
   <path>` — the README's whole 30-second quickstart — and open the resulting `report.json` as an
   issue or a PR. That is rung 1, done.
2. **An eval case** — an input that should be caught, or should not be, with the expected
   verdict. This is how a guard stops regressing.
3. **A policy** — a rule plus the mechanism that enforces it, honestly labelled as enforced or
   advisory.
4. **An adapter** — support for one more agent, matched to what that agent's hooks can really do.
   Here that means one more target entry in `src/context_report/data/payloads-v0.1.json` and
   `bundle-layout-v0.1.json` (a target agent's plugin-bundle layout), or one more `Asker` backend
   registered in `PROVIDERS` in `src/context_report/run/runner.py` (a model `run` and `judge` can
   actually reach).
5. **Review** — reading someone else's evidence and saying whether it holds.

**Becoming a maintainer:** three merged pull requests earns triage rights — labelling, closing
duplicates, and asking for the evidence a report is missing. Nobody is asked to commit to more
than they want to.

This project runs its own chock policies (`.chock/`, the same `protect-main-branch` rule
dogfooded below) plus DCO sign-off, on every pull request, and that pair is the filter for
low-effort machine-generated contributions — not a human gatekeeper. A PR that cannot say what it
checked will not pass, whoever or whatever wrote it.

## Development setup

```bash
# 1. Fork the repo on GitHub, then clone YOUR fork
git clone https://github.com/<your-username>/context-report.git
cd context-report

# 2. Install editable with dev dependencies (Python 3.10-3.13 supported; CI runs all four).
pip install -e '.[dev]'
```

CI installs the same packages from `requirements/ci.txt`, which pins every third-party package by
hash (`pip install --require-hashes`), then the package itself with `--no-deps`. The other files
under `requirements/` do the same for the build, Pages and semgrep jobs. To change a pin, edit the
`.in` file and regenerate:

```
pip-compile --generate-hashes --allow-unsafe --strip-extras -o requirements/ci.txt requirements/ci.in
```

```bash
# 3. Verify your environment — everything below should pass
python -m ruff check .               # lint
python -m ruff format --check .      # format
python -m pytest -q                  # test suite

# Also run the suite under the oldest supported interpreter before sending a PR:
PYTHONPATH=src python3.10 -m pytest -q
```

If those are green, you're ready to build.

## Branch & pull request workflow

We keep `main` clean and protected — in fact, **this repo enforces that on itself**
(you cannot commit straight to `main`; that's the `protect-main-branch` policy
dogfooding). So always work on a branch.

**1. Branch naming** — `type/short-description`:

| Prefix | Use for |
| :--- | :--- |
| `feat/` | New feature (`feat/add-cost-row`) |
| `fix/` | Bug fix (`fix/schema-inputhash-format`) |
| `docs/` | Documentation only (`docs/readme-quickstart`) |
| `test/` / `chore/` | Tests or tooling |

**2. Commit messages** — [Conventional Commits](https://www.conventionalcommits.org):

```text
feat(produce): add context_tokens cost row
fix(verify): recompute inputHash before comparing
docs(readme): clarify the efficacy extra
```

**3. Open the PR** against `main`, describe **what** changed and **why**, and make sure
**CI is green**. One reviewer approval merges it; we aim to give first feedback within a
few days.

## Sign your commits (DCO)

This project uses the [Developer Certificate of Origin](https://developercertificate.org/) (DCO)
instead of a CLA: no paperwork, no copyright assignment — a one-line trailer on each commit
certifying you have the right to contribute the change under the project's license
(Apache-2.0).

Add the trailer with the `-s` flag:

```bash
git commit -s -m "fix(verify): recompute inputHash before comparing"
```

which appends:

```text
Signed-off-by: Your Name <your.email@example.com>
```

CI checks every commit on a PR for the trailer. Forgot one? Amend and force-push your branch:

```bash
git commit --amend -s --no-edit && git push --force-with-lease
```

(or for several commits, `git rebase --signoff main`). The name and email must be real enough
to stand behind — the sign-off is you certifying the DCO, not a formality.

**Automate it** so you never discover the requirement via a CI rejection: install
[pre-commit](https://pre-commit.com) once, then enable the `commit-msg` hook this repo
ships (`.pre-commit-config.yaml`) —

```bash
pip install pre-commit
pre-commit install --hook-type commit-msg
```

— and every commit gets the `Signed-off-by` trailer automatically from your `git config
user.name` / `user.email`, whether or not you remembered `-s`.

## Agent-authored code

**Use an agent if you want to. Every change still gets read by a human before it merges,
including ours.**

Worth saying out loud rather than leaving to be inferred. Much of this repository was written
with Claude Code — the `Co-Authored-By` trailers are in the log and are not going to be quietly
dropped. A project that reports on whether agent-produced artifacts actually work and is coy
about having used one has a credibility problem; a project that uses one without review has a
worse one.

The rule is symmetric, and it is about the review rather than the author:

- **Disclose it.** Keep the `Co-Authored-By` trailer your tool adds. Nobody will think less of
  the PR for it.
- **A human reads the whole diff before merge.** Not the summary, and not just the changed
  hunks. This applies to maintainer PRs too — there is no fast path for ours.
- **You are the author.** "The agent wrote it" is not an explanation for a change you cannot
  defend in review. If you could not answer a question about a line, take that line out.

Two places where review will be slower on purpose:

- **`spec/`, and anything that changes what a `basis` or a row's schema means.** This is the
  format's honesty contract, and every consumer trusts it unread.
- **`src/context_report/verify.py`.** It decides what "re-derivable" actually re-derives. An
  agent optimising for a green suite will usually find the claim easier to change than the
  check, and that is the one edit this project cannot afford to wave through.

This is the policy for at least the project's first months. If it changes, it changes here,
with a reason.

## Project conventions

See [CONVENTIONS.md](CONVENTIONS.md) for the house style (docstrings, templating, static
analysis). In short:

- One-line docstring per module, class and function; a comment only where the code is
  genuinely non-obvious.
- Never a blanket `ruff --fix` — review each rule category on its own against the tests.
- Facts about the world (vendor names, field mappings) go in JSON the code reads, not in
  branching logic.

## Labels — where to start

Browse issues by label to find your entry point:

- [`good first issue`](https://github.com/open-coder-ai/context-report/labels/good%20first%20issue) — small, well-scoped, and mentored. **Start here.**
- [`help wanted`](https://github.com/open-coder-ai/context-report/labels/help%20wanted) — we'd love a hand.
- `bug` — confirmed defects.
- `documentation` — no code required.

The [open, seeded good-first-issue
list](https://github.com/open-coder-ai/context-report/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
is maintained separately from this file — expect the kind of thing in "Good first contributions"
below: a missing target's payload shape, a citation to source, a `NotAvailable` row worth closing.

Comment on an issue to claim it — we'll assign it to you so no one double-works.

## Good first contributions

Concrete, scoped starting points found in the code and the measurement paper — each names the
file it lives in, so you can go straight there instead of hunting:

1. **Add a fifth target agent's payload shape.** `src/context_report/data/payloads-v0.1.json`
   covers four target agents (`claude_code`, `codex_cli`, `copilot`, `cursor`). Adding another
   (Windsurf, Zed, Gemini CLI, Amazon Q Developer CLI, ...) means sourcing its PreToolUse-equivalent
   payload shape — event key, tool key, deny path — from the vendor's own docs, and grading the
   entry's `basis` honestly (`vendor-docs` versus `live-run`, per the file's own header comment).
2. **Source `codex_cli`'s documented fault behaviour.** `DOCUMENTED_FAULT_BEHAVIOUR` in
   `src/context_report/produce/fault.py` has entries for `claude_code`, `copilot`, and `cursor`,
   but not `codex_cli` — the paper's §5.4 table records its fault posture as "unconfirmed in
   sources." Finding and citing the vendor documentation closes that row.
3. **A producer that drives a live client for the three fault rows.** `client_dependent_rows()` in
   `src/context_report/produce/fault.py` reports `fault.scriptMissing`, `fault.interpreterMissing`,
   and `fault.timeout` as `NotAvailable` because v0.1 never drives a real agent client — the one
   measurement the paper's conclusion (§8) names as coming next.
4. **Implement `decision` replay.** `src/context_report/produce/run.py` (around line 291) always
   emits the `decision` row as `NotAvailable`, "no declared positive/negative cases were supplied;
   v0.1 has no decision replay." Table 3 of the paper describes the intended shape: replay declared
   cases against the guard, per OpenAI's 5-positive/3-negative contract shape.
5. **Measure `interference` against declared co-installed artifacts.** `src/context_report/produce/run.py`
   (around line 300) always reports `interference` as `NotAvailable`, "v0.1 producer does not
   measure interference." Extending chock's own shadowed-rule check, as the paper's method table
   (§4) describes, is the starting point.
6. **A tokenizer that isn't an approximation.** `context_tokens_row()` in
   `src/context_report/produce/cost.py` counts tokens with `approx-regex-v1` — a word/punctuation
   regex, not a provider's real tokenizer. The paper's own threats-to-validity section (§6) names
   the resulting error as unmeasured; wiring in a real tokenizer (behind a new `method` value, so
   `approx-regex-v1` statements stay reproducible) would close that gap.
7. **Implement `arms.mode: "leave-one-out"`.** `src/context_report/data/run-v0.1.schema.json`
   accepts the value, but `src/context_report/run/runner.py` (line 102) raises
   `RunError("arms.mode 'leave-one-out' is not implemented in v0.1; use 'isolated'")`.
   `spec/run/v0.1/README.md` describes the intended semantics: all subjects installed together,
   each ablated in turn while the others stay in place.
8. **Another instruction-file or skill sample.** `paper/measurements/instruction-sample/` holds
   seven real-world artifacts (its own `README.md` explains the selection rule). Measuring an
   eighth the same way — a fresh clone at a pinned commit, run through `context-report produce`
   and, for efficacy, the run manifest under `efficacy/` — and adding it to that directory's
   `SUMMARY.md` extends the sample without touching the format itself.

## Figures

Every figure under `docs/figures/` is generated from this repository's own data by a script here,
shipped as a light and a dark SVG, and regenerated in CI so a stale figure fails the build. If you
are changing one, read the standard first — it explains the palette, why absence is never drawn as
a weak grade, and why colour is never the only carrier of meaning:

https://github.com/open-coder-ai/.github/blob/main/VISUAL.md

`docs/figures/palette.py` and `make_family.py` are shared across every open-coder-ai repository and
carried byte-identically. Change them at the source and copy them out; never edit one copy, and
never add a per-repo lint or format exclude to work around them.

## Code of Conduct

Be kind, be curious, assume good faith. The full text is in
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) (Contributor Covenant 2.1), including how to
report an incident.

**Welcome aboard.**
