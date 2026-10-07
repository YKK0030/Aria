# Aria + Attic integration

Aria connects to Attic through the Attic FastMCP server. Aria does not call
Attic REST endpoints directly. Attic's internal HTTP implementation stays
behind MCP.

Attic is Aria’s durable secondary brain:

```text
WhatsApp / Telegram
        ↓
Aria agent core
   ├─ Redis: short-term turns and TTL
   ├─ Attic: durable facts, decisions, docs, preferences, citations
   └─ tools/channels: actions and delivery
```

## Why use both

- Redis is fast and temporary; it should hold the recent chat window.
- Attic is inspectable, searchable, exportable, tenant-scoped, and durable.
- Aria should not stuff the whole conversation into every prompt.
- Attic results carry source and citation metadata so the agent can distinguish
  evidence from instructions.

## Start Attic locally

From the sibling `Attic` repository:

```sh
cd ../Attic
ollama pull all-minilm
ollama pull qwen2.5:0.5b-instruct
OLLAMA_HOST=0.0.0.0:11434 ollama serve
docker compose -f docker/docker-compose.yml up --build
```

Attic runs at `http://localhost:4000` with development key `dev-key`.

## Aria configuration

Add these values to `.env` when Phase 02 is implemented:

```env
ATTIC_ENABLED=false
ATTIC_MCP_URL=http://attic-mcp:4100/mcp
ATTIC_API_KEY=dev-key
ATTIC_NAMESPACE=aria:personal
```

Run `attic-mcp` beside Attic and put both services on the same Compose network.

## Integration shape

Use one small MCP adapter in `agent_core/memory/attic.py`:

```python
from agno.tools.mcp import MCPTools

attic_tools = MCPTools(
    transport="streamable-http",
    url=settings.attic_mcp_url,
    tool_name_prefix="attic",
    timeout_seconds=10,
    refresh_connection=True,
)
```

Recommended Aria flow:

1. Load Redis turns for immediate conversational context.
2. Recall Attic only for durable facts relevant to the inbound message.
3. Mark recalled content as untrusted evidence in the prompt.
4. After a useful exchange, remember only durable outcomes—not every token.
5. Include Attic source IDs in summaries and admin inspection views.

## Namespace and source conventions

Use a stable namespace per deployment, tenant, or user boundary:

```text
aria:user:<user-id>
aria:chat:<channel>:<chat-id>
aria:tenant:<tenant-id>
```

Useful sources:

```text
aria:whatsapp
aria:telegram
aria:summary
aria:tool:<tool-name>
aria:document:<path>
```

Never store passwords, API keys, session tokens, or raw credentials in either
Aria or Attic.

## Rollout plan

1. Add config values and a disabled-by-default Attic MCP connection.
2. Keep SQLite as history and audit storage; do not duplicate every message.
3. Compare recall quality and latency on real conversations.
4. Make Attic the durable read path after the comparison passes.
5. Retire duplicate long-term storage only after export and rollback are proven.

## What Aria should add next

Prioritized improvements:

1. Human approval for sensitive tool actions and outbound messages.
2. A single identity/tenant model shared by channels and Attic namespaces.
3. Structured tool permissions, timeouts, retries, and idempotency keys.
4. Evaluation fixtures for response quality, memory precision, and prompt
   injection resistance.
5. OpenTelemetry/structured event tracing across gateway, agent, Redis, and
   Attic.
6. Scheduled reminders and jobs with explicit user consent.
7. Attachment/document ingestion into Attic with source citations.
8. Admin UI for memory review, forget, approval, and audit history.

Do not remove Aria’s Redis short-term layer until Attic-backed retrieval has
been measured in production-like conversations.
