# context-report

An open, signed report format for one question: **does this agent context artifact actually
work?** `context-report` is an [in-toto](https://github.com/in-toto/attestation) predicate an
author produces in their own CI and a catalog verifies at submission.

- Spec: [attestation/v0.1/](attestation/v0.1/)

## Predicate type

```
https://open-coder-ai.github.io/context-report/attestation/v0.1
```

## Verifying an attestation

```
gh attestation verify <artifact> \
  --predicate-type https://open-coder-ai.github.io/context-report/attestation/v0.1 \
  --signer-workflow open-coder-ai/context-report/.github/workflows/attest.yml@main
```
