# Phase 03 — Tool system

## Includes

- Keep one small Python file per local tool under `tools/`.
- Load tools into Agno from type hints and docstrings.
- Keep external service tools behind MCP.
- Add timeout, validation, safe errors, and tool allowlisting.
- Add approval metadata for sensitive tools.

## Behavior

Adding a tool means adding one file. Removing a tool means removing one file.
Agent code does not change.

## Verification

- Example tool loads locally and in Docker.
- Invalid input fails safely.
- Tool timeout returns a useful error.
- Tool failure does not crash a conversation.

## Exit gate

One-file tool addition works end to end.
