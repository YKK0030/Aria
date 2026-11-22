# Dynamic Tools

Add one small Python file here for each local Agno tool.

Each tool should expose a typed `run(...)` function and a useful docstring.
Files in this folder are trusted executable code; never place user uploads here.
Set `TOOL_ENABLED = True` to explicitly allow a tool. Tools marked
`TOOL_APPROVAL_REQUIRED = True` stay unavailable until Phase 06 adds approval
routing. External service-owned tools belong behind MCP instead of this folder.

Minimum format:

```python
TOOL_NAME = "hello_tool"
TOOL_DESCRIPTION = "Returns a simple greeting."
TOOL_ENABLED = True
TOOL_APPROVAL_REQUIRED = False
TOOL_TIMEOUT_SECONDS = 5

def run(name: str = "world") -> str:
    return f"Hello, {name}!"
```

Optional:

- `ARGS_SCHEMA`: a Pydantic model for structured arguments
- `async def arun(...)`: async version
- `TOOL_TIMEOUT_SECONDS`: maximum runtime, greater than 0 and at most 60 seconds (default 10)

Invalid metadata or imports keep the tool unavailable and write a safe log.
Tool errors return safe messages. A timed-out synchronous function can keep
running in a bounded worker thread; use only trusted, bounded code here.
The agent reloads tools automatically when files in this folder change.
