from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool

from agent_core.config import settings


class DynamicToolRegistry:
    def __init__(self) -> None:
        self._fingerprint: tuple[tuple[str, float], ...] = ()
        self._tools: list[BaseTool] = []
        self._tool_specs: list[dict[str, str]] = []

    def get_tools(self) -> list[BaseTool]:
        fingerprint = self._compute_fingerprint()
        if fingerprint != self._fingerprint:
            self._tools, self._tool_specs = self._load_tools()
            self._fingerprint = fingerprint
        return list(self._tools)

    def list_tool_specs(self) -> list[dict[str, str]]:
        self.get_tools()
        return list(self._tool_specs)

    def _compute_fingerprint(self) -> tuple[tuple[str, float], ...]:
        tools_dir = settings.resolved_tools_dir
        if not tools_dir.exists():
            return ()
        files = sorted(path for path in tools_dir.glob("*.py") if path.name != "__init__.py")
        return tuple((str(path), path.stat().st_mtime) for path in files)

    def _load_tools(self) -> tuple[list[BaseTool], list[dict[str, str]]]:
        tools: list[BaseTool] = []
        specs: list[dict[str, str]] = []
        tools_dir = settings.resolved_tools_dir
        if not tools_dir.exists():
            tools_dir.mkdir(parents=True, exist_ok=True)
            return tools, specs

        for path in sorted(tools_dir.glob("*.py")):
            if path.name == "__init__.py":
                continue
            loaded = self._load_tool_from_file(path)
            if not loaded:
                continue
            tool, spec = loaded
            tools.append(tool)
            specs.append(spec)
        return tools, specs

    def _load_tool_from_file(self, path: Path) -> tuple[BaseTool, dict[str, str]] | None:
        module = self._load_module(path)
        if not module:
            return None

        name = getattr(module, "TOOL_NAME", path.stem)
        description = getattr(module, "TOOL_DESCRIPTION", f"Dynamic tool loaded from {path.name}")
        run_fn = getattr(module, "run", None)
        args_schema = getattr(module, "ARGS_SCHEMA", None)

        if not callable(run_fn):
            return None

        try:
            tool = StructuredTool.from_function(
                func=run_fn,
                coroutine=getattr(module, "arun", None),
                name=name,
                description=description,
                args_schema=args_schema,
                infer_schema=args_schema is None,
            )
        except Exception:
            return None

        return tool, {"name": name, "description": description, "source": str(path)}

    @staticmethod
    def _load_module(path: Path) -> ModuleType | None:
        module_name = f"dynamic_tool_{path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if not spec or not spec.loader:
                return None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        except Exception:
            return None


dynamic_tool_registry = DynamicToolRegistry()
