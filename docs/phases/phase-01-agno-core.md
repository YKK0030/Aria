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
event → duplicate check → Redis context → Agno agent → response result
```

Missing Groq credentials allow built-in commands and fallback replies.

## Verification

- `/help`, `/status`, `/note`, and `/todo` work without Groq.
- Normal request works with Groq.
- Redis failure does not crash the agent.

## Exit gate

WhatsApp and Telegram can call one Agno runtime method.
