# Phase 04 — Channel adapters

Status: **Implementation verified; WhatsApp live smoke pending pairing.** Both
adapters feed the shared `AgentOrchestrator`/`AgentRuntime`; the local WhatsApp
gateway is running but not paired. Telegram is deferred by user request.

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

- Agent-core tests prove WhatsApp and Telegram events use the same runtime and
  send via their channel-specific adapters.
- Duplicate event produces no second runtime call or reply.
- Adapter tests verify Telegram allowlisting and WhatsApp webhook
  authentication reject unauthorized inbound requests.
- Agent-core suite: 17 tests passed in Docker with current source/tests/tools
  mounted; `git diff --check` passed.
- Live WhatsApp receive/send remains pending: pair the gateway and configure
  the allowed phone number. Telegram receive/send is deferred by user request.
  No channel message was sent during Phase 02 verification.

## Exit gate

WhatsApp behaves consistently without channel logic inside the agent, and its
live receive/send smoke test passes. Telegram remains deferred.
