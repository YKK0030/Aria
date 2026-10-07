# Dynamic Tools

Add one small Python file here for each local Agno tool.

Each tool should expose a typed `run(...)` function and a useful docstring.
Validate inputs, use timeouts for external calls, and return safe errors.
Sensitive tools require approval. External service-owned tools belong behind
FastMCP instead of this folder.

Minimum format:

```python
TOOL_NAME = "hello_tool"
TOOL_DESCRIPTION = "Returns a simple greeting."

def run(name: str = "world") -> str:
    return f"Hello, {name}!"
```

Optional:

- `ARGS_SCHEMA`: a Pydantic model for structured arguments
- `async def arun(...)`: async version

The agent reloads tools automatically when files in this folder change.
