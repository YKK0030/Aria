from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from pydantic import BaseModel, Field, ValidationError

from agent_core.config import settings
from agent_core.tooling.loader import DynamicToolRegistry


class ToolRegistryTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.tools_dir = Path(self.temp_dir.name)
        self.generated_dir = self.tools_dir / "generated"
        self.project_tools_dir = settings.tools_dir
        self.registry = DynamicToolRegistry()
        self.settings_patch = patch.object(settings, "tools_dir", str(self.tools_dir))
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)
        self.generated_patch = patch.object(settings, "generated_tools_dir", str(self.generated_dir))
        self.generated_patch.start()
        self.addCleanup(self.generated_patch.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def add_tool(self, filename: str, source: str) -> None:
        (self.tools_dir / filename).write_text(source, encoding="utf-8")

    async def test_one_file_tool_loads_in_langchain_and_agno(self) -> None:
        self.add_tool(
            "hello.py",
            """
TOOL_NAME = "hello"
TOOL_DESCRIPTION = "Return greeting."
TOOL_ENABLED = True
TOOL_APPROVAL_REQUIRED = False
def run(name: str = "world") -> str:
    return f"Hello, {name}!"
""",
        )

        local_tool = self.registry.get_tools()[0]
        self.assertEqual(await local_tool.ainvoke({"name": "Ada"}), "Hello, Ada!")

        agno_tool = self.registry.get_agno_tools()[0]
        agno_result = await agno_tool.entrypoint(name="Ada")
        self.assertIn("Hello, Ada!", str(agno_result))

    async def test_checked_in_example_tool_loads_from_project_tools_directory(self) -> None:
        registry = DynamicToolRegistry()
        with patch.object(settings, "tools_dir", self.project_tools_dir):
            tools = {tool.name: tool for tool in registry.get_tools()}
        self.assertEqual(await tools["hello_tool"].ainvoke({}), "Hello, world!")

    async def test_voice_and_test_scripts_are_not_loaded_as_tools(self) -> None:
        self.add_tool("test_helper.py", 'raise RuntimeError("test files are not tools")\n')
        self.add_tool("aria_voice.py", 'raise RuntimeError("voice app is not a tool")\n')
        self.assertEqual(self.registry.get_tools(), [])
        self.assertEqual(self.registry.list_tool_specs(), [])

    async def test_disabled_and_approval_required_tools_are_not_exposed(self) -> None:
        self.add_tool(
            "disabled.py",
            'TOOL_NAME="disabled"\nTOOL_DESCRIPTION="Disabled."\ndef run() -> str: return "no"\n',
        )
        self.add_tool(
            "sensitive.py",
            'TOOL_NAME="sensitive"\nTOOL_DESCRIPTION="Sensitive."\nTOOL_ENABLED=True\n'
            'TOOL_APPROVAL_REQUIRED=True\ndef run() -> str: return "no"\n',
        )

        self.assertEqual(self.registry.get_tools(), [])
        specs = {spec["name"]: spec for spec in self.registry.list_tool_specs()}
        self.assertFalse(specs["disabled"]["available"])
        self.assertFalse(specs["sensitive"]["available"])
        self.assertEqual(self.registry.get_agno_tools(), [])

    async def test_timeout_and_failure_return_safe_tool_results(self) -> None:
        self.add_tool(
            "slow.py",
            'import asyncio\nTOOL_NAME="slow"\nTOOL_DESCRIPTION="Slow."\n'
            'TOOL_ENABLED=True\nTOOL_TIMEOUT_SECONDS=0.01\n'
            'def run() -> str: return "sync"\n'
            'async def arun() -> str:\n    await asyncio.sleep(0.1)\n    return "late"\n',
        )
        self.add_tool(
            "slow_sync.py",
            'import time\nTOOL_NAME="slow_sync"\nTOOL_DESCRIPTION="Slow sync."\n'
            'TOOL_ENABLED=True\nTOOL_TIMEOUT_SECONDS=0.01\n'
            'def run() -> str:\n    time.sleep(0.1)\n    return "late"\n',
        )
        self.add_tool(
            "broken.py",
            'TOOL_NAME="broken"\nTOOL_DESCRIPTION="Broken."\nTOOL_ENABLED=True\n'
            'def run() -> str: raise RuntimeError("private detail")\n',
        )

        tools = {tool.name: tool for tool in self.registry.get_tools()}
        timeout = await tools["slow"].ainvoke({})
        sync_timeout = tools["slow_sync"].invoke({})
        failure = await tools["broken"].ainvoke({})
        self.assertIn("timed out", timeout)
        self.assertIn("timed out", sync_timeout)
        self.assertIn("failed safely", failure)
        self.assertNotIn("private detail", failure)

    async def test_schema_rejects_invalid_input_before_tool_runs(self) -> None:
        self.add_tool(
            "validated.py",
            'from pydantic import BaseModel, Field\n'
            'class Args(BaseModel):\n    count: int = Field(gt=0)\n'
            'TOOL_NAME="validated"\nTOOL_DESCRIPTION="Validated input."\n'
            'TOOL_ENABLED=True\nARGS_SCHEMA=Args\n'
            'def run(count: int) -> str: return str(count)\n',
        )
        tool = self.registry.get_tools()[0]

        with self.assertRaises(ValidationError):
            await tool.ainvoke({"count": 0})

    async def test_delete_removes_only_generated_tool_and_refreshes_registry(self) -> None:
        self.generated_dir.mkdir()
        generated = self.generated_dir / "temporary.py"
        generated.write_text(
            'TOOL_NAME="temporary"\nTOOL_DESCRIPTION="Temporary."\n'
            'TOOL_ENABLED=True\ndef run() -> str: return "ok"\n',
            encoding="utf-8",
        )
        self.assertIn("temporary", {tool.name for tool in self.registry.get_tools()})

        removed = self.registry.delete_generated_tool("temporary")

        self.assertEqual(removed["name"], "temporary")
        self.assertFalse(generated.exists())
        self.assertNotIn("temporary", {tool.name for tool in self.registry.get_tools()})
        with self.assertRaises(FileNotFoundError):
            self.registry.delete_generated_tool("temporary")
