## What

<!-- One-paragraph summary of the change and which finding/requirement it addresses. -->

## Definition of done

- [ ] `python -m ruff check .` and `python -m ruff format --check .` clean
- [ ] `python -m pytest -q` green; new checks have attack + ordinary-data tests
- [ ] Schema changes: `spec/attestation/v0.1/schema.json` and its example stay in sync
- [ ] `chock check` and `chock sync --repo . --check` clean, if `.agents/policies/` changed

## Claims

- [ ] No row is described as `re-derivable` unless it actually recomputes from the subject
      plus its recorded configuration and carries an `inputHash`. A row that could not be
      measured says `NotAvailable`, `Error`, or `NotApplicable` and why.
