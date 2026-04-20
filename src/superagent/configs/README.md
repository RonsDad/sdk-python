# Superagent configuration files

Config in this package is split into **two types**, as documented in the
top-level design:

## Type 1 — Agent config (`../agent_config.json`)

Validated by `AGENT_CONFIG_SCHEMA` at
`strands/experimental/agent_config.py:22`. It is `additionalProperties: False`
— i.e. the schema is strict and only accepts `name` / `model` / `prompt` /
`tools`. This file defines **who** the agent is: its identity, system
prompt, and preloaded tool roster. It **must not** carry any provider
wiring, business logic, or runtime kwargs.

## Type 2 — Model config (`./model.<provider>.json`)

One file per provider. Consumed by
`superagent.model_providers.factory.build_model`, which constructs a
`strands.models.Model` instance. The dict shape is:

```json
{
  "provider": "<key from PROVIDERS>",
  "model_id": "<provider-specific id>",
  "api_key": "<optional; otherwise read from env>",
  "params": { "<provider-specific native kwargs>": "..." },
  "client_args": { "<overrides passed to the underlying SDK client>": "..." },
  "native_tools": [ "<provider-native server-side tools>" ]
}
```

### Provider → env var for API key (if `api_key` is omitted)

| provider           | env var                        |
|--------------------|--------------------------------|
| `anthropic`        | `ANTHROPIC_API_KEY`            |
| `bedrock`          | AWS credential chain           |
| `gemini`           | `GEMINI_API_KEY`               |
| `openai`           | `OPENAI_API_KEY`               |
| `openai_responses` | `OPENAI_API_KEY`               |
| `mistral`          | `MISTRAL_API_KEY`              |
| `litellm`          | per downstream provider        |
| `xai`              | `XAI_API_KEY`                  |
| `zai`              | `ZAI_API_KEY`                  |
| `moonshot`         | `MOONSHOT_API_KEY`             |
| `deepseek`         | `DEEPSEEK_API_KEY`             |
| `alibaba`          | `DASHSCOPE_API_KEY`            |
| `nim`              | `NVIDIA_API_KEY`               |
| `vercel`           | `VERCEL_AI_GATEWAY_API_KEY`    |
| `perplexity`       | `PERPLEXITY_API_KEY`           |

### Native server-side tools

Where the SDK supports it (`BedrockModel`, `GeminiModel`,
`OpenAIResponsesModel`, and our `PerplexityAgentModel`), native
server-side tools are passed via `params` or `native_tools`. These run
inside the provider and stream back as part of the model response —
they do not appear in the agent's function-tool roster.

### Reasoning levels

Reasoning is opt-in per provider and lives under `params`:

- **Anthropic** (`claude-opus-4.*`, `claude-sonnet-4.*`):
  `params.thinking = {"type": "enabled", "budget_tokens": 8000}`.
- **Gemini**: `params.thinking_config = {"thinking_budget": 4096}`.
- **OpenAI (`o*`/`gpt-5`/`gpt-5-codex`)**:
  `params.reasoning = {"effort": "low|medium|high"}`.
- **OpenAI Responses / xAI grok-4**: same `params.reasoning` shape.
- **Deepseek** reasoner: set `model_id = "deepseek-reasoner"`.
- **Alibaba Qwen** (`qwen3-*`): `params.enable_thinking = true`.
- **Z.ai** (`glm-4.6`+): `params.thinking = {"type": "enabled"}`.
- **Perplexity** (`sonar-reasoning-pro`): handled by model choice.
