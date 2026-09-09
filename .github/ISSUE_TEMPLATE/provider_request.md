---
name: New model provider
about: Request or propose a backend for `context-report run` / `judge`
labels: enhancement
---

**Provider name** (as it would appear in `PROVIDERS`, e.g. `bedrock`):

**Does it speak the OpenAI chat-completions shape?**
<!-- If yes, `openai-compatible` + `--base-url` may already cover it -- say why it doesn't. -->

**How is a prompt sent and the answer read back?**
<!-- HTTP endpoint + request/response shape, or a local CLI's argv and stdout, as
     `OpenAICompatibleAsker`/`CliAsker` show in `src/context_report/efficacy/`. -->

**Auth** (API key env var, local login, none):

**Does it report token usage?** (input/output/cached -- `last_usage`, if so, in what shape)

**Does it report which model actually answered?** (`last_model`, e.g. an alias resolving to a
pinned version)

**Any field `ModelRef` doesn't have yet** (like `openai-compatible`'s `baseUrl`/`apiKeyEnv`):

**Documentation link:**
