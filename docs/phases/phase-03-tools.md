# Phase 03 — Tool system

Status: **Complete**. Phase 02 remains parked; this phase does not change the
model provider or enable Ollama.

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

- Checked-in example tool loads from `tools/`.
- A temporary one-file tool loads and executes through both Agno and LangChain.
- Disabled and approval-required tools are withheld.
- Invalid input, async/sync timeout, and tool exceptions return safe failures.
- Agent-core test suite: 12 tests passed in the existing Docker test image with
  current source mounted; `git diff --check` passed.

Fresh Docker image rebuild was attempted but PyPI download timed out. Retry it
when network access is available; the mounted-source tests passed independently.

## Exit gate

One-file tool addition works end to end.

## Handoff

Local Python modules under `tools/` are trusted code. Timeouts bound the caller
wait, but cannot stop an already-running synchronous function; keep tool code
trusted and lightweight. Approval enforcement remains for Phase 06.
