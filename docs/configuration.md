# Aria configuration

## Rule

`.env.example` is the complete local configuration template. Copy it to `.env`
before starting services.

## Groups

| Group | Important variables |
|---|---|
| Runtime | `APP_ENV`, `LOG_LEVEL`, `AGENT_HOST`, `AGENT_PORT` |
| Models | `GROQ_API_KEY`, `GROQ_SIMPLE_MODEL`, `GROQ_COMPLEX_MODEL` |
| WhatsApp | `WHATSAPP_*` |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_IDS` |
| Redis | `REDIS_ENABLED`, `REDIS_URL`, `SHORT_TERM_MEMORY_*` |
| SQLite | `LONG_TERM_MEMORY_DB_PATH`, `MAX_HISTORY_MESSAGES` |
| Tools | `TOOLS_DIR`, `ENABLE_COMMANDS` |
| Attic MCP | `ATTIC_ENABLED`, `ATTIC_MCP_URL`, `ATTIC_API_KEY`, `ATTIC_NAMESPACE` |
| Admin | `ADMIN_API_KEY`, `ENABLE_AUDIT_LOGGING` |

## Attic defaults

Attic is disabled by default. Enable it only after Attic MCP is running:

```env
ATTIC_ENABLED=true
ATTIC_MCP_URL=http://attic-mcp:4100/mcp
ATTIC_API_KEY=change-me
ATTIC_NAMESPACE=aria:personal
```

Aria talks to Attic through MCP. `ATTIC_API_KEY` is passed to the Attic MCP
connection, not used by an Aria REST client.

## Secret rules

- Never commit `.env`.
- Use `.env.example` for names and safe defaults only.
- Do not put secrets in prompts, memory, audit logs, or tool results.
- Production secrets come from the deployment secret store.
