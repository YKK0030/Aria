# Aria + Attic integration

Aria connects to Attic through the Attic FastMCP server. Aria does not call
Attic REST endpoints directly. Attic's internal HTTP implementation stays
behind MCP.

Attic is Aria’s durable secondary brain:

```text
WhatsApp / Telegram
        ↓
Aria agent core
   ├─ Valkey (Redis protocol): short-term turns and TTL
   ├─ Attic: durable facts, decisions, docs, preferences, citations
   └─ tools/channels: actions and delivery
```

## Why use both

- Valkey is fast and temporary; it should hold the recent chat window.
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

Configure Attic's MCP server with its backend key and namespace:

```env
ATTIC_API_KEY=dev-key
ATTIC_MCP_API_KEY=replace-me
ATTIC_NAMESPACE=aria:personal
ATTIC_MCP_HOST=0.0.0.0
```

Install and run the MCP server beside Attic:

```sh
cd ../Attic/packages/mcp_server
python3 -m pip install -e .
ATTIC_URL=http://localhost:4000 \
ATTIC_API_KEY=dev-key \
ATTIC_MCP_API_KEY=replace-me \
ATTIC_NAMESPACE=aria:personal \
ATTIC_MCP_HOST=0.0.0.0 \
python3 -m attic_mcp.server
```

The Aria container reaches this host process at
`http://host.docker.internal:4100/mcp`.

FastMCP validates HTTP Host/Origin by default. The stock server returned HTTP
421 for `host.docker.internal:4100`; the current Attic worktree resolves this
with a narrow `TransportSecuritySettings` allowlist for the Docker host and
origin. Keep validation enabled. `ATTIC_MCP_HOST=0.0.0.0` only controls the
bind address; it does not change this security allowlist.

Semantic recall also requires the API's embedding provider to be reachable.
Host Ollama listens on `127.0.0.1:11434`, which Docker containers cannot reach
through `host.docker.internal`. The verified test used a temporary `socat`
forwarder bound only to Docker gateway `172.17.0.1:11434`; remember returned one
vector and recall returned the saved marker. This forwarder is temporary and
does not survive reboot. Production needs a managed route bound only to Docker's
host gateway or an embedding service on a private Compose network.

Set these values in Aria's `.env`:

```env
ATTIC_ENABLED=false
ATTIC_MCP_URL=http://host.docker.internal:4100/mcp
ATTIC_MCP_API_KEY=replace-me
```

## Integration shape

Use one small MCP adapter in `agent_core/memory/attic.py`:

```python
from agent_core.memory.attic import connect_attic

async with connect_attic() as attic_tools:
    # Pass connected tools to the Agno agent when available.
    ...
```

Recommended Aria flow:

1. Load Valkey turns for immediate conversational context.
2. Offer Attic recall only for durable facts relevant to the inbound message.
3. Mark recalled content as untrusted evidence in the prompt.
4. After a useful exchange, remember only durable outcomes—not every token.
5. Preserve Attic source IDs when returning recalled evidence.

## Namespace and source conventions

Set a stable namespace on the Attic MCP server per deployment boundary:

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

The MCP server pins its configured namespace; Aria cannot override it. Use a
single-user namespace only for a single-user deployment. Multi-user scope needs
a trusted identity-to-namespace mapping before enabling Attic.

Never store passwords, API keys, session tokens, or raw credentials in either
Aria or Attic. The `forget` tool stays unavailable to the agent until Phase 06
adds approval for destructive actions.

## Rollout plan

1. Complete: add config and disabled-by-default Attic MCP adapter.
2. Keep SQLite as history and audit storage; do not duplicate messages in Attic.
3. Verify `remember`, `recall`, and `health` against a running Attic MCP server;
   require nonzero vectors and a successful read-back, not merely tool success.
4. Compare recall quality and latency on real conversations.
5. Add trusted identity-to-namespace isolation before multi-user enablement.
6. Expose `forget` after Phase 06 adds destructive-action approval.
7. Make Attic the durable read path only after quality and rollback checks pass.

## What Aria should add next

Prioritized improvements:

1. Human approval for sensitive tool actions and outbound messages.
2. A single identity/tenant model shared by channels and Attic namespaces.
3. Structured tool permissions, timeouts, retries, and idempotency keys.
4. Evaluation fixtures for response quality, memory precision, and prompt
   injection resistance.
5. OpenTelemetry/structured event tracing across gateway, agent, Valkey, and
   Attic.
6. Scheduled reminders and jobs with explicit user consent.
7. Attachment/document ingestion into Attic with source citations.
8. Admin UI for memory review, forget, approval, and audit history.

Do not remove Aria’s Valkey short-term layer until Attic-backed retrieval has
been measured in production-like conversations.
