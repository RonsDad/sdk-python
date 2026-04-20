# Superagent configuration files

Config is split into **two types**:

## Type 1 — Agent config (`../agent_config.json`)

Validated by `AGENT_CONFIG_SCHEMA` at `strands/experimental/agent_config.py:22`
(strict: `additionalProperties: False`). Accepts only `name` / `model` /
`prompt` / `tools`. This file defines **who** the agent is. It must not
carry provider wiring or runtime kwargs.

## Type 2 — Model config (`./model.<provider>.json`)

One empty template per provider. Consumed by
`superagent.model_providers.factory.build_model`, which returns a
`strands.models.Model` instance. The values in these templates are
intentionally blank — they are filled in by the UI (or by the user
directly). The only fixed field is `provider`, which selects the
factory entry.

Common template shape:

```json
{
  "provider": "<provider key>",
  "api_key": "",
  "model_id": "",
  "params": {},
  "client_args": {}
}
```

If `api_key` is left blank, the factory falls back to the
provider-specific env var.

## Built-in providers

`anthropic`, `bedrock`, `gemini`, `mistral`, `litellm`, `openai`,
`openai_responses`, `xai`, `zai`, `moonshot`, `deepseek`, `alibaba`,
`nim`, `vercel`, `perplexity`.
