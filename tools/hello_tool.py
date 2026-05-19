TOOL_NAME = "hello_tool"
TOOL_DESCRIPTION = "Simple example tool that returns a greeting."


def run(name: str = "world") -> str:
    return f"Hello, {name}!"

