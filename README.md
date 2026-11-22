# Aria — Multi-Channel AI Agent

> **Development status:** Aria is under active development. WhatsApp,
> Telegram, model, memory, and tool integrations should be tested in your own
> environment before production use.

This repository is scaffolded as a two-service backend:

- `services/whatsapp-gateway`: Node.js gateway for WhatsApp session management, filtered inbound events, send APIs, and read receipts.
- `services/agent-core`: Python FastAPI service using Agno and Groq for reasoning, plus Telegram bot integration. The previous LangGraph runtime remains available for rollback.
- `tools`: repo-root dynamic Python tools directory that auto-loads into the agent

## What this scaffold already supports

- WhatsApp allowlisting by number, group JID, and optional group name
- Receiving WhatsApp messages only from selected groups and numbers
- Sending and marking WhatsApp messages as read through a protected API
- Forwarding inbound WhatsApp events to the Python agent core
- Telegram bot polling with allowed chat filtering
- Telegram slash commands now flow through the agent command system
- Channel-neutral Agno runtime for incoming WhatsApp and Telegram messages
- Groq-backed LLM integration via Agno; `langchain-groq` remains for LangGraph rollback
- Automatic Groq model routing: `llama-3.1-8b-instant` for simple tasks and `llama-3.3-70b-versatile` for complex tasks
- Valkey-backed short-term memory with the latest 4 turns
- Local SQLite-backed long-term graph memory with top-5 node retrieval
- Dynamic repo-root `tools/` loading into the agent toolset
- Bounded DuckDuckGo search and public-page retrieval through `web_search`
- Duplicate inbound message protection
- Built-in agent commands like `/help`, `/status`, `/channels`, `/memory`, and `/echo`
- Built-in note taking with `/note add|list|clear`
- Built-in todo tracking with `/todo add|list|done|clear`
- AI-powered conversation summaries with `/summary`
- File-based conversation history and audit logging
- Admin APIs for status, manual outbound messaging, and history inspection
- Admin capability endpoint for dashboard or control plane use
- Optional JSON access policy file for second-layer channel filtering
- Config-first structure for adding more tools later

## Architecture

```text
WhatsApp <-> Node Gateway (Baileys/Fastify) ---> Agent Core (FastAPI/Agno/Groq/Tools)
                                              ^                          |
Telegram Bot ---------------------------------|                          v
                                      Valkey Short-Term Memory    SQLite Graph Memory
```

## Why this split

- Node is a better fit for WhatsApp Web session handling with Baileys.
- Python is a good fit for Agno and tool-heavy agent workflows.
- The services communicate through HTTP so we can swap pieces later without rewriting everything.
- The Agno runtime uses the faster `8b` Groq model for lightweight messages and escalates to `70b` for more complex reasoning.
- Root `.env` is discovered automatically for local development in both services.
- SQLite is used for long-term memory because it is local, lightweight, zero-ops, and a better fit than Postgres for this phase.

## Local startup (Linux)

Aria runs locally with Docker Compose and Ollama. Start Attic separately if
you want durable memory; the full setup and stop commands are in
[docs/local-startup.md](docs/local-startup.md). Attic also has its own
[startup guide](https://github.com/YKK0030/attic#try-it-in-5-minutes).

On first setup only, copy `.env.example` to `.env` and configure local keys.
Then choose one or more channels (or `all`):

```sh
ollama pull llama3.2
python3 tools/aria start --channels cli,web,telegram
```

That one command starts the selected background channels and opens CLI. Add
`--voice` to use voice instead of CLI; choose `--channels web,telegram` for
background services only. Telegram needs a bot token and allowed chat IDs;
WhatsApp needs pairing and an allowed number. Open the command centre at
`http://127.0.0.1:8001/command-center`; see [docs/local-startup.md](docs/local-startup.md).

For WhatsApp, pair the gateway and configure an allowed number before sending
messages. Telegram remains optional and is not needed for local Ollama testing.
Aria can draft reusable task tools during local CLI/web sessions. `tools review`
automatically runs sandbox tests and a separate reviewer agent, then asks for
your approval; see [docs/task-tools.md](docs/task-tools.md).
For public internet information, ask Aria to search the web or provide a public
URL to read. Search queries go to DuckDuckGo; page retrieval blocks private/local
hosts, redirects, non-text content, and responses over 1 MB.

Task prompts live in `services/agent-core/src/agent_core/prompts/`. Aria selects
a small task-specific addition (research, coding, writing, or tool creation)
from the current request; edit the matching prompt file to tune it.

Conversation history and audit events are stored locally under
`.data/agent-core/`. Attic is an optional memory service, not Aria's log store;
Aria only writes durable memories there when its memory tools are configured
and used.

## Important notes

- For WhatsApp, this scaffold uses Baileys. It is practical for private automation, but it is not the official Meta Business API.
- Group IDs usually look like `1203630xxxxxxxx@g.us`.
- Individual users are normalized into WhatsApp JIDs from the phone numbers you place in `WHATSAPP_ALLOWED_NUMBERS`.
- Telegram is set up in polling mode for now to keep local development simple.
- Runtime history and audit files are written under `.data/agent-core`.
- In Docker Compose, agent history and policy config are mounted from the host so they persist across restarts.
- Valkey runs as a short-term memory cache service in Docker Compose.

## Admin endpoints

- `GET /health`: service health
- `POST /chat`: submit a prompt to Aria from the authenticated web/API channel
- `GET /admin/status`: agent configuration and runtime status
- `POST /admin/messages/send`: manually send a message to WhatsApp or Telegram
- `GET /admin/history/{channel}/{chat_id}`: inspect recent history for a chat
- `GET /admin/capabilities`: list assistant capabilities
- `GET /admin/tools`: list dynamically loaded tools
- `GET /admin/graph/search`: search long-term graph memory
- `GET /admin/graph/node/{id}`: inspect one node and its relations
- `GET /admin/graph/chat/{channel}/{chat_id}`: inspect recent chat graph nodes and edges
- `GET /admin/graph-ui`: lightweight web UI for graph exploration

## Model Routing

- `llama-3.1-8b-instant` is used for short and simple tasks
- `llama-3.3-70b-versatile` is used for summaries and more complex tasks
- Complexity is detected from message length, amount of recent context, multiline/code-like prompts, and reasoning-heavy keywords

## Memory Layers

- Short-term memory: Valkey cache with the last 4 turns per chat, injected into the LLM context
- Long-term memory: local SQLite graph memory storing durable message nodes and edges
- Retrieval: top 5 long-term nodes are fetched by relevance when the model decides to call the graph-memory tool
- Graph linking: each chat message sequence is linked, and inbound/outbound pairs are linked with a `response` edge
- Tool-aware retrieval: the model can choose whether to use graph memory, so long-term memory does not always consume extra context tokens

## Durable secondary brain: Attic

Aria uses [Attic](https://github.com/YKK0030/attic) as the planned durable
memory layer. Keep Valkey for short-term conversation context; use Attic for
facts, preferences, decisions, documents, summaries, and cross-channel memory.

Integration guide: [docs/attic-integration.md](docs/attic-integration.md).

## Dynamic Tools

- Put one typed Python tool file under the repo-root [tools/](tools/) folder
- Tools are auto-discovered and exposed to the agent
- The example tool is [hello_tool.py](tools/hello_tool.py)
- This is the extension point you can use later for backend actions, internal APIs, automation, and utility scripts

## Built-in commands

- `/help`
- `/status`
- `/channels`
- `/memory`
- `/capabilities`
- `/echo <text>`
- `/note add <text>`
- `/note list`
- `/note clear`
- `/todo add <text>`
- `/todo list`
- `/todo done <id>`
- `/todo clear`
- `/summary`

## Implemented backend capabilities

- Read-only tools for allowlisted internal backend APIs.
- Owner approval queue for sensitive actions.
- Dynamic channel allowlist management through authenticated admin APIs.
- Persistent recurring reminders and scheduled jobs.
- Search over repository documentation with file and line citations.
- Structured JSON events, request/trace correlation, and optional OpenTelemetry.

See [observability setup](docs/observability.md) for tracing configuration.
