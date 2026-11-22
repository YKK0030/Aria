# Phase 09 — Production operation

## Includes

- Public HTTPS FastMCP endpoint.
- OAuth or equivalent MCP authentication.
- Backups for Attic, SQLite, Qdrant, Valkey, and WhatsApp session data.
- Structured logs and request IDs.
- Metrics for latency, tool errors, memory errors, and channel delivery.
- Restore drill.
- Credential rotation procedure.

## Behavior

Attic outage, Qdrant outage, or Ollama outage must not corrupt chat history or
stop command handling.

## Exit gate

Deployment, rollback, backup, restore, and credential rotation are tested.
