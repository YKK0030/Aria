# Aria architecture

## Goal

Personal AI assistant with WhatsApp and Telegram channels, fast context,
durable memory, simple tools, approvals, and an MCP surface for external AI
clients.

## Runtime

```text
WhatsApp / Telegram
        |
        v
FastAPI channel ingress
        |
        v
Agno agent
  |       |        |
  |       |        +-- Local Python tools
  |       +----------- Attic MCP: durable memory
  +------------------- Valkey: recent turns
        |
        +-- Aria SQLite: history, graph, audit
        |
        v
Channel response

ChatGPT / MCP client
        |
        v
Aria FastMCP /mcp
        |
        v
Agno agent
```

## Ownership

| Component | Owns |
|---|---|
| FastAPI | Internal channel webhooks, health, lifecycle |
| FastMCP | External assistant/tool boundary |
| Agno | Agent execution, tool calls, approvals |
| Internal API tool | Read-only status, capabilities, tool registry, and scheduled-job APIs |
| Valkey (Redis protocol) | Last four turns and TTL context |
| Aria SQLite | Conversation history, graph edges, audit logs |
| Attic | Durable facts, preferences, decisions, notes, documents |
| Qdrant/Ollama | Attic semantic indexing and local embeddings |

## Non-goals

- No direct Aria-to-Attic REST client.
- No public CRUD REST API for agent operations.
- No multi-agent team until one agent is insufficient.
- No automatic storage of every conversation in Attic.
- No tool that bypasses approval for sensitive actions.
- Internal API tools call only allowlisted read routes; they do not expose history or mutation APIs.

## Memory rule

Valkey answers: “What is happening now?”

Attic answers: “What should Aria remember later?”

SQLite answers: “What happened and how do we audit it?”

Attic outage must not stop normal chat.
