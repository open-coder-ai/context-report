# CLI: `run` and `compare`

Beyond `produce` and `verify` (see the README's quickstart), `context-report` drives whole
measurement manifests and compares runs over time.

## Running a manifest

The optional `context-report[efficacy]` extra pulls in the `anthropic` client for the `efficacy`
row (`context-report efficacy --help`). `context-report run` reads a JSON manifest matching
[`spec/run/v0.1/schema.json`](../spec/run/v0.1/schema.json) — see
[`spec/run/v0.1/examples/run.json`](../spec/run/v0.1/examples/run.json) for a worked one (two
subjects, four models across the three providers, three tasks) — and supports `--dry-run` (rules and call budget, no model
touched), `--n` (override `arms.nPerArm` for a smoke run), and `--resume` (continue the latest run,
reusing every existing statement and matching transcript, calling only for the rest). Two providers
have a backend: `anthropic` (the API) and `claude-cli` (the local `claude` CLI, so one manifest can
compare `opus`/`sonnet`/`fable`); any other subject model gets an honest `NotAvailable` efficacy
row instead of a guess.

## Every model you can reach

Subject models come from the manifest, never from code: `anthropic`, `claude-cli`, or
`openai-compatible` with a `baseUrl`, which is any server speaking the chat-completions shape,
hosted (OpenAI, Gemini, Mistral, Groq) or local (Ollama, vLLM, LM Studio). One manifest lines up
every model you can reach; the API-shaped ones answer without tools or a checkout, which the run
spec states.
