# Phase 05 — FastMCP surface

## Includes

- Add FastMCP server for Aria.
- Expose `/mcp` through Streamable HTTP.
- Expose high-level tools only: ask, memory search, remember, forget,
  capabilities.
- Connect Agno to Attic through `MCPTools`.
- Do not expose internal SQLite or raw channel operations.

## Behavior

```text
ChatGPT MCP client → Aria FastMCP → Agno → tools/memory → result
```

## Verification

- MCP client discovers tools.
- `ask` reaches the same runtime as WhatsApp and Telegram.
- Memory namespace comes from authenticated identity.
- Unauthorized calls fail.

## Exit gate

ChatGPT can use Aria through MCP without a public REST API.
