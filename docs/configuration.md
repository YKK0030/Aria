# Aria configuration

## Rule

`.env.example` is the complete local configuration template. Copy it to `.env`
before starting services.

## Groups

| Group | Important variables |
|---|---|
| Runtime | `APP_ENV`, `LOG_LEVEL`, `AGENT_HOST`, `AGENT_PORT`, `ARIA_CHANNELS` |
| Models | `GROQ_API_KEY`, `GROQ_SIMPLE_MODEL`, `GROQ_COMPLEX_MODEL` |
| WhatsApp | `WHATSAPP_*`; `WHATSAPP_OWNER_NUMBERS` separately enables owner-only approvals in private chats |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_IDS` (required allowlist for chat, notifications, and owner controls) |
| Valkey (Redis protocol) | `REDIS_ENABLED`, `REDIS_URL`, `SHORT_TERM_MEMORY_*` |
| SQLite | `LONG_TERM_MEMORY_DB_PATH`, `MAX_HISTORY_MESSAGES` |
| Tools | `TOOLS_DIR`, `GENERATED_TOOLS_DIR`, `TOOL_PROPOSALS_DIR`, `ENABLE_COMMANDS` |
| Attic MCP | `ATTIC_ENABLED`, `ATTIC_MCP_URL`, `ATTIC_MCP_API_KEY` |
| Aria MCP | `MCP_API_KEY`, `MCP_IDENTITY` |
| Admin | `ADMIN_API_KEY`, `ENABLE_AUDIT_LOGGING` |

## Aria MCP

Set a strong `MCP_API_KEY` to enable the Streamable HTTP endpoint at
`http://localhost:8000/mcp`. `MCP_IDENTITY` is the fixed identity used to scope
MCP memory; the initial bearer key maps to that one identity. Add any non-local
host (including its port, if present) to `MCP_ALLOWED_HOSTS`; DNS-rebinding
protection stays enabled. Multi-user OAuth and token-derived identities remain
Phase 06 work.

## Attic defaults

Attic is disabled by default. Enable it only after Attic MCP is running:

```env
ATTIC_ENABLED=true
ATTIC_MCP_URL=http://host.docker.internal:4100/mcp
ATTIC_MCP_API_KEY=replace-with-attic-mcp-api-key
```

Aria sends `ATTIC_MCP_API_KEY` as a bearer token to Attic MCP. Configure the
separate `ATTIC_API_KEY` and `ATTIC_NAMESPACE` on the Attic MCP server; Aria
does not call Attic's REST API or choose a namespace from message content.

## Secret rules

- Never commit `.env`.
- Use `.env.example` for names and safe defaults only.
- Do not put secrets in prompts, memory, audit logs, or tool results.

For NVIDIA, `NVIDIA_SUPER_MODEL`, `NVIDIA_CODE_MODEL`, and `NVIDIA_ROBOTICS_MODEL`
are model-card IDs used by Aria's main agent and read-only specialists. The
robotics setting defaults to NVIDIA's Nemotron 3.5 Lightning 30B endpoint; it
can be changed to another currently available NIM model card. Free endpoint
availability changes, so check NVIDIA's catalog before changing it. Aria does
not automatically download or activate arbitrary models from web search.
- Production secrets come from the deployment secret store.
