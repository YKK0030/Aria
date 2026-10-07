# Phase 04 — Channel adapters

## Includes

- WhatsApp and Telegram call the same agent runtime.
- FastAPI handles internal WhatsApp webhook and health endpoints.
- Telegram keeps polling for local simplicity.
- Preserve channel-specific send implementations.
- Preserve duplicate protection and allowlists.

## Behavior

```text
channel event → shared runtime → channel-specific response
```

## Verification

- WhatsApp receive/send smoke test passes.
- Telegram receive/send smoke test passes.
- Duplicate event produces no second reply.
- Unauthorized event is rejected.

## Exit gate

Both channels behave consistently without channel logic inside the agent.
