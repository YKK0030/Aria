# Dynamic Tools

Add Python files here to expose new LangChain/LangGraph tools to the agent.

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

