# Phase 08 — Docker deployment

## Includes

Services:

```text
redis
qdrant
ollama
attic
attic-mcp
agent-core
whatsapp-gateway
```

- Health checks.
- Persistent volumes.
- Pinned dependencies.
- Separate development and production environment files.
- No public database ports in production.

## Behavior

Start dependencies before agent runtime. A missing optional dependency must
degrade cleanly or fail with a clear startup message.

## Exit gate

Fresh checkout starts from documented commands and survives restart.
