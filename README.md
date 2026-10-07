# Aria — Multi-Channel AI Agent

> **Development status:** Aria is under active development. WhatsApp,
> Telegram, model, memory, and tool integrations should be tested in your own
> environment before production use.

This repository is scaffolded as a two-service backend:

- `services/whatsapp-gateway`: Node.js gateway for WhatsApp session management, filtered inbound events, send APIs, and read receipts.
- `services/agent-core`: Python FastAPI service using LangChain, LangGraph, and Groq for reasoning, plus Telegram bot integration.
- `tools`: repo-root dynamic Python tools directory that auto-loads into the agent

## What this scaffold already supports

- WhatsApp allowlisting by number, group JID, and optional group name
- Receiving WhatsApp messages only from selected groups and numbers
- Sending and marking WhatsApp messages as read through a protected API
- Forwarding inbound WhatsApp events to the Python agent core
- Telegram bot polling with allowed chat filtering
- Telegram slash commands now flow through the agent command system
- LangGraph workflow that can process incoming WhatsApp and Telegram messages
- Groq-backed LLM integration via `langchain-groq`
- Automatic Groq model routing: `llama-3.1-8b-instant` for simple tasks and `llama-3.3-70b-versatile` for complex tasks
- Redis-backed short-term memory with the latest 4 turns
- Local SQLite-backed long-term graph memory with top-5 node retrieval
- Dynamic repo-root `tools/` loading into the agent toolset
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
WhatsApp <-> Node Gateway (Baileys/Fastify) ---> Agent Core (FastAPI/LangGraph/Groq/Tools)
                                              ^                          |
Telegram Bot ---------------------------------|                          v
                                        Redis Short-Term Memory    SQLite Graph Memory
```

## Why this split

- Node is a better fit for WhatsApp Web session handling with Baileys.
- Python is a better fit for LangChain, LangGraph, and future tool-heavy agent workflows.
- The services communicate through HTTP so we can swap pieces later without rewriting everything.
- The agent core automatically uses the faster `8b` Groq model for lightweight messages and escalates to `70b` for more complex reasoning.
- Root `.env` is discovered automatically for local development in both services.
- SQLite is used for long-term memory because it is local, lightweight, zero-ops, and a better fit than Postgres for this phase.

## Setup

1. Copy `.env.example` to `.env` and fill in the secrets.
2. Optionally copy `config/access-policy.example.json` to `config/access-policy.json` and customize behavior.
3. Start everything with one command.
4. Authenticate WhatsApp by scanning the QR shown by the gateway service, or use pairing if configured.

## One Command Startup

```powershell
npm run dev
```

That command starts:

- Redis
- WhatsApp gateway
- Python agent core

## Local Run

### WhatsApp gateway

```powershell
cd services/whatsapp-gateway
npm install
npm run dev
```

### Agent core

```powershell
cd services/agent-core
python -m venv .venv
.venv\Scripts\activate
pip install -e .
uvicorn agent_core.main:app --reload --host 0.0.0.0 --port 8000
```

## Docker Compose

```powershell
docker compose up --build
```

## Important notes

- For WhatsApp, this scaffold uses Baileys. It is practical for private automation, but it is not the official Meta Business API.
- Group IDs usually look like `1203630xxxxxxxx@g.us`.
- Individual users are normalized into WhatsApp JIDs from the phone numbers you place in `WHATSAPP_ALLOWED_NUMBERS`.
- Telegram is set up in polling mode for now to keep local development simple.
- Runtime history and audit files are written under `.data/agent-core`.
- In Docker Compose, agent history and policy config are mounted from the host so they persist across restarts.
- Redis runs as a short-term memory cache service in Docker Compose.

## Admin endpoints

- `GET /health`: service health
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

- Short-term memory: Redis cache with the last 4 turns per chat, injected into the LLM context
- Long-term memory: local SQLite graph memory storing durable message nodes and edges
- Retrieval: top 5 long-term nodes are fetched by relevance when the model decides to call the graph-memory tool
- Graph linking: each chat message sequence is linked, and inbound/outbound pairs are linked with a `response` edge
- Tool-aware retrieval: the model can choose whether to use graph memory, so long-term memory does not always consume extra context tokens

## Durable secondary brain: Attic

Aria uses [Attic](https://github.com/YKK0030/attic) as the planned durable
memory layer. Keep Redis for short-term conversation context; use Attic for
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

## Next steps

- Add tool calling for your internal backend APIs
- Add human approval routing for sensitive actions
- Add dynamic allowlist management from admin APIs
- Add recurring reminders and scheduled jobs
- Add retrieval over your internal docs or SOPs
- Add observability with OpenTelemetry and structured event logs
