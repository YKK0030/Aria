TOOL_NAME = "hello_tool"
TOOL_DESCRIPTION = "Simple example tool that returns a greeting."
TOOL_ENABLED = True
TOOL_APPROVAL_REQUIRED = False
TOOL_TIMEOUT_SECONDS = 5


def run(name: str = "world") -> str:
    return f"Hello, {name}!"

