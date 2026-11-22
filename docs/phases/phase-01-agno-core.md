# Phase 01 — Agno agent core

## Includes

- Add Agno dependency.
- Add `agent_core/agent.py` for one primary agent.
- Add `agent_core/runtime.py` for channel-neutral execution.
- Move prompt templates into `agent_core/prompts/`.
- Keep built-in commands as normal Python functions.
- Preserve Groq model routing and fallback behavior.

## Behavior

```text
event → duplicate check → Valkey context → Agno agent → response result
```

Missing Groq credentials allow built-in commands and fallback replies.

## Verification

- `/help`, `/status`, `/note`, and `/todo` pass in the agent container without Groq.
- No-key fallback passes; unavailable Valkey does not block `/help`.
- Agent image builds; FastAPI imports; Agno accepts the repo's dynamic tool; LangGraph rollback compiles.
- Both channel handlers call the same `AgentRuntime.run` method.
- Live Groq inference remains unverified because no API key is configured.

## Exit gate

WhatsApp and Telegram call one Agno runtime method.

## Current status

Complete. Both channel handlers call `AgentRuntime.run`; Docker build and offline smoke checks pass. Live Groq inference and channel end-to-end delivery remain unverified without credentials and a running gateway. Keep LangGraph and its dependencies for rollback until live inference passes.
