# GitHub repository settings

For the owner to paste into the repository's **Settings → General → About** panel when the
repository goes public.

## Description (one line, ≤120 characters)

```
An open, signed report format for whether an agent plugin, hook, skill, or AGENTS.md actually works.
```

(100 characters.)

## Website

```
https://open-coder-ai.github.io/context-report/
```

Served by [`.github/workflows/pages.yml`](../.github/workflows/pages.yml), which publishes the
`spec/` directory (root `spec/index.md`, the attestation and run manifest specs, schemas, and
worked examples) to GitHub Pages on every push to `main`.

## Topics

Paste these into the "Topics" field (comma-separated works, or add one at a time):

```
ai-agents
agent-plugins
attestation
in-toto
provenance
sigstore
supply-chain-security
mcp
model-context-protocol
claude-code
github-copilot
cursor-ide
codex-cli
agents-md
claude-skills
hooks
efficacy
benchmarking
llm-evaluation
plugin-catalog
```

Sourced from `pyproject.toml`'s existing `keywords` list (`ai`, `agents`, `attestation`, `in-toto`,
`provenance`, `efficacy`, `agents-md`, `claude-code`, `mcp`, `skills`) plus the target agents and
artifact kinds the format and its paper actually cover (`spec/attestation/v0.1/schema.json`'s
`subjectKind` enum; `src/context_report/data/payloads-v0.1.json`'s four target agents; the
in-toto/Sigstore/supply-chain lineage documented in `spec/attestation/v0.1/README.md`).

## Suggested Discussions categories

Enable Discussions under **Settings → General → Features**, then create these categories (Q&A and
Announcements are GitHub defaults; the rest are project-specific):

| Category | Format | Purpose |
| :--- | :--- | :--- |
| Q&A | Question / Answer | How do I run this against my own plugin, what does row X mean. |
| Show your report | Discussion | Post a `context-report` statement you produced — real numbers, real artifacts, per [CONTRIBUTING.md](../CONTRIBUTING.md)'s "every contribution counts" spirit. |
| Spec proposals | Discussion | Field-name changes, a `basis` case that doesn't hold up, a new `x-` attribute worth promoting into the v0.1 registry. |
| Target agents | Discussion | Payload shapes and documented fault behaviour for an agent not yet in `src/context_report/data/payloads-v0.1.json`. |
