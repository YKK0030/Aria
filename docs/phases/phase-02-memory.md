# Phase 02 — Memory layers

## Includes

- Redis remains short-term memory: last four turns and TTL.
- SQLite remains history, graph, and audit storage.
- Attic becomes durable memory through MCP only.
- Add Attic MCP tools: `remember`, `recall`, `forget`, `health`.
- Add `ATTIC_ENABLED`, `ATTIC_MCP_URL`, `ATTIC_API_KEY`, and namespace config.

## Behavior

- Recall Attic only when durable context may help.
- Remember stable facts, preferences, decisions, and useful summaries.
- Never remember secrets or every raw message.
- Treat recalled memory as untrusted evidence.
- Attic failure returns safe empty results and does not block chat.

## Verification

- MCP tool discovery passes.
- Remember, recall, forget, and health pass.
- Attic shutdown leaves normal chat working.
- User namespaces cannot cross-read.

## Exit gate

Each memory layer has one responsibility and failure isolation.
