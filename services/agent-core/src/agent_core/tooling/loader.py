from __future__ import annotations

import asyncio
import inspect
import importlib.util
import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from langchain_core.tools import BaseTool, StructuredTool

from agent_core.config import settings

logger = logging.getLogger(__name__)
_TOOL_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="agent-tool")


class DynamicToolRegistry:
    def __init__(self) -> None:
        self._fingerprint: tuple[tuple[str, int, int], ...] = ()
        self._tools: list[BaseTool] = []
        self._tool_specs: list[dict[str, Any]] = []
        self._agno_fingerprint: tuple[tuple[str, int, int], ...] = ()
        self._agno_tools: list[Any] = []

    def get_tools(self) -> list[BaseTool]:
        fingerprint = self._compute_fingerprint()
        if fingerprint != self._fingerprint:
            self._tools, self._tool_specs = self._load_tools()
            self._fingerprint = fingerprint
        return list(self._tools)

    def list_tool_specs(self) -> list[dict[str, Any]]:
        self.get_tools()
        return list(self._tool_specs)

    def delete_generated_tool(self, name: str) -> dict[str, Any]:
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,47}", name):
            raise ValueError("Invalid generated tool name")
        path = settings.resolved_generated_tools_dir / f"{name}.py"
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError(name)
        module = self._load_module(path)
        metadata = self._metadata(module, path) if module else None
        if not metadata or metadata["name"] != name or metadata["source"] != path.name:
            raise ValueError("Refusing to remove a file that is not a registered generated tool")
        path.unlink()
        self._fingerprint = ()
        self._agno_fingerprint = ()
        return metadata

    def get_agno_tools(self) -> list[Any]:
        from agno.tools import tool as agno_tool

        fingerprint = self._compute_fingerprint()
        if fingerprint != self._agno_fingerprint:
            tools = []
            for path in self._tool_files():
                module = self._load_module(path)
                if not module:
                    continue
                metadata = self._metadata(module, path)
                if not metadata or not metadata["available"]:
                    continue
                function = getattr(module, "arun", None) or getattr(module, "run", None)
                guarded = self._async_wrapper(function, metadata)
                tools.append(agno_tool(name=metadata["name"], description=metadata["description"])(guarded))
            self._agno_tools = tools
            self._agno_fingerprint = fingerprint
        return list(self._agno_tools)

    def _compute_fingerprint(self) -> tuple[tuple[str, int, int], ...]:
        paths = self._tool_files()
        directories = (settings.resolved_tools_dir, settings.resolved_generated_tools_dir)
        return tuple((str(path), 0, 0) for path in directories) + tuple(
            (str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in paths
        )

    @staticmethod
    def _tool_files() -> list[Path]:
        directories = (settings.resolved_tools_dir, settings.resolved_generated_tools_dir)
        return sorted(
            path
            for tools_dir in directories
            for path in tools_dir.glob("*.py")
            if path.name != "__init__.py"
            and (tools_dir != settings.resolved_tools_dir or not path.name.startswith("test_"))
            and (tools_dir != settings.resolved_tools_dir or path.name != "aria_voice.py")
        )

    def _load_tools(self) -> tuple[list[BaseTool], list[dict[str, Any]]]:
        tools: list[BaseTool] = []
        specs: list[dict[str, Any]] = []
        settings.resolved_tools_dir.mkdir(parents=True, exist_ok=True)
        for path in self._tool_files():
            module = self._load_module(path)
            metadata = self._metadata(module, path) if module else None
            if not metadata:
                continue
            specs.append({key: value for key, value in metadata.items() if key != "args_schema"})
            if not metadata["available"]:
                continue
            tool = self._create_langchain_tool(module, metadata)
            if tool:
                tools.append(tool)
        return tools, specs

    @staticmethod
    def _metadata(module: ModuleType, path: Path) -> dict[str, Any] | None:
        name = getattr(module, "TOOL_NAME", path.stem)
        description = getattr(module, "TOOL_DESCRIPTION", f"Local tool from {path.name}.")
        enabled = getattr(module, "TOOL_ENABLED", False)
        approval_required = getattr(module, "TOOL_APPROVAL_REQUIRED", False)
        timeout = getattr(module, "TOOL_TIMEOUT_SECONDS", 10)
        if (
            not isinstance(name, str)
            or not name.strip()
            or not isinstance(description, str)
            or not description.strip()
            or not isinstance(enabled, bool)
            or not isinstance(approval_required, bool)
            or isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout)
            or not 0 < timeout <= 60
        ):
            logger.warning("Invalid metadata in local tool %s", path.name)
            return None
        function = getattr(module, "arun", None) or getattr(module, "run", None)
        if not callable(function):
            logger.warning("Local tool %s has no callable run/arun", path.name)
            return None
        return {
            "name": name,
            "description": description,
            "source": path.name,
            "enabled": enabled,
            "approval_required": approval_required,
            "available": enabled and not approval_required,
            "timeout_seconds": float(timeout),
            "args_schema": getattr(module, "ARGS_SCHEMA", None),
        }

    @staticmethod
    def _validated_arguments(schema: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
        if schema is None:
            return kwargs
        instance = schema(**kwargs)
        return instance.model_dump() if hasattr(instance, "model_dump") else instance.dict()

    @classmethod
    def _async_wrapper(cls, function: Callable[..., Any], metadata: dict[str, Any]) -> Callable[..., Any]:
        name = metadata["name"]
        timeout = metadata["timeout_seconds"]
        schema = metadata["args_schema"]

        async def invoke(**kwargs: Any) -> Any:
            try:
                arguments = cls._validated_arguments(schema, kwargs)
                if inspect.iscoroutinefunction(function):
                    return await asyncio.wait_for(function(**arguments), timeout=timeout)
                loop = asyncio.get_running_loop()
                # shortcut: timed-out sync calls keep running in the bounded worker; use process isolation for untrusted tools.
                return await asyncio.wait_for(
                    loop.run_in_executor(_TOOL_EXECUTOR, partial(function, **arguments)),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning("Local tool %s timed out after %.2f seconds", name, timeout)
                return f"Tool {name} timed out after {timeout:g} seconds."
            except Exception as error:
                logger.error("Local tool %s failed (%s)", name, type(error).__name__)
                return f"Tool {name} failed safely. Check agent logs for details."

        return cls._set_signature(invoke, function, schema, name, metadata["description"])

    @classmethod
    def _sync_wrapper(cls, function: Callable[..., Any], metadata: dict[str, Any]) -> Callable[..., Any]:
        name = metadata["name"]
        timeout = metadata["timeout_seconds"]
        schema = metadata["args_schema"]

        def invoke(**kwargs: Any) -> Any:
            try:
                arguments = cls._validated_arguments(schema, kwargs)
                return _TOOL_EXECUTOR.submit(function, **arguments).result(timeout=timeout)
            except TimeoutError:
                logger.warning("Local tool %s timed out after %.2f seconds", name, timeout)
                return f"Tool {name} timed out after {timeout:g} seconds."
            except Exception as error:
                logger.error("Local tool %s failed (%s)", name, type(error).__name__)
                return f"Tool {name} failed safely. Check agent logs for details."

        return cls._set_signature(invoke, function, schema, name, metadata["description"])

    @classmethod
    def _set_signature(
        cls,
        wrapper: Callable[..., Any],
        function: Callable[..., Any],
        schema: Any,
        name: str,
        description: str,
    ) -> Callable[..., Any]:
        signature = cls._signature(function, schema)
        wrapper.__name__ = name
        wrapper.__doc__ = description
        wrapper.__signature__ = signature
        wrapper.__annotations__ = {
            parameter.name: parameter.annotation
            for parameter in signature.parameters.values()
            if parameter.annotation is not inspect.Parameter.empty
        }
        if signature.return_annotation is not inspect.Signature.empty:
            wrapper.__annotations__["return"] = signature.return_annotation
        return wrapper

    @staticmethod
    def _signature(function: Callable[..., Any], schema: Any) -> inspect.Signature:
        if schema is None:
            return inspect.signature(function)
        fields = getattr(schema, "model_fields", None) or getattr(schema, "__fields__", {})
        parameters = []
        for field_name, field in fields.items():
            is_required = getattr(field, "is_required", None)
            required = is_required() if callable(is_required) else getattr(field, "required", False)
            default = inspect.Parameter.empty if required else field.default
            parameters.append(
                inspect.Parameter(
                    field_name,
                    inspect.Parameter.KEYWORD_ONLY,
                    default=default,
                    annotation=getattr(field, "annotation", getattr(field, "outer_type_", Any)),
                )
            )
        return inspect.Signature(parameters, return_annotation=Any)

    @classmethod
    def _create_langchain_tool(cls, module: ModuleType, metadata: dict[str, Any]) -> BaseTool | None:
        function = getattr(module, "run", None)
        async_function = getattr(module, "arun", None) or function
        if not callable(function) or not callable(async_function):
            return None
        try:
            return StructuredTool.from_function(
                func=cls._sync_wrapper(function, metadata),
                coroutine=cls._async_wrapper(async_function, metadata),
                name=metadata["name"],
                description=metadata["description"],
                args_schema=metadata["args_schema"],
                infer_schema=metadata["args_schema"] is None,
            )
        except Exception:
            logger.exception("Could not register local tool %s", metadata["name"])
            return None

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
            logger.exception("Could not load local tool %s", path.name)
            return None


dynamic_tool_registry = DynamicToolRegistry()
