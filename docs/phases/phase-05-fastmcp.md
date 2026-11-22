# Phase 05 — FastMCP surface

Status: **In progress.** Phase 04 live-channel smoke checks are deferred; its
adapter-level tests pass.

## Includes

- Add FastMCP server for Aria.
- Expose `/mcp` through Streamable HTTP.
- Expose high-level tools only: ask, memory search, remember, forget,
  capabilities.
- Connect Agno to Attic through `MCPTools`.
- Do not expose internal SQLite or raw channel operations.
- Keep MCP memory scoped to the authenticated identity; initial local bearer
  key maps to one configured identity until Phase 06 adds user-level auth.

## Behavior

```text
ChatGPT MCP client → Aria FastMCP → Agno → tools/memory → result
```

## Verification

- An in-memory MCP client discovers exactly the five intended tools and calls
  `ask` through the shared `AgentOrchestrator`/`AgentRuntime`.
- Memory tools use only the configured identity's namespace; deleting another
  identity's memory is rejected.
- HTTP bearer middleware rejects missing/invalid credentials.
- `/mcp` Streamable HTTP initialization returns 200 with a valid key and 503
  when MCP is not configured; existing `/health` remains available.
- Agent-core suite: 22 tests passed in the existing Docker image with current
  source/tests/tools mounted; Python compilation and `git diff --check` pass.
- ChatGPT cloud connection is deferred until a reachable HTTPS deployment is
  available; Phase 06 will replace the initial single-identity key with proper
  user-level authentication.

## Exit gate

ChatGPT can use Aria through MCP without a public REST API.
