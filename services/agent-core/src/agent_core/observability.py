from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

from agent_core.config import settings

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("aria_request_id", default="")
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("aria_trace_id", default="")
logger = logging.getLogger("aria.events")
_tracing_state: dict[str, Any] = {"configured": False, "exporter_configured": False}


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_var.get()
        trace_id = current_trace_id() or trace_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        if trace_id:
            payload["trace_id"] = trace_id
        fields = getattr(record, "aria_event", None)
        if isinstance(fields, dict):
            payload["event"] = fields
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.StreamHandler(sys.stdout))
    for handler in root.handlers:
        handler.setFormatter(JsonLogFormatter())
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))


def set_request_context(request_id: str | None = None) -> tuple[contextvars.Token, contextvars.Token]:
    rid = request_id if request_id and re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", request_id) else uuid.uuid4().hex
    trace_id = current_trace_id()
    return request_id_var.set(rid), trace_id_var.set(trace_id)


def reset_request_context(tokens: tuple[contextvars.Token, contextvars.Token]) -> None:
    request_id_var.reset(tokens[0])
    trace_id_var.reset(tokens[1])


def current_request_id() -> str:
    return request_id_var.get()


def current_trace_id() -> str:
    try:
        from opentelemetry import trace

        context = trace.get_current_span().get_span_context()
        if context.is_valid:
            return format(context.trace_id, "032x")
    except Exception:
        pass
    return ""


def emit_event(name: str, level: int = logging.INFO, **fields: Any) -> None:
    logger.log(level, name, extra={"aria_event": {"name": name, **fields}})


def start_agent_span(channel: str, model: str, route: str):
    from opentelemetry import trace

    return trace.get_tracer("aria.agent").start_as_current_span(
        "aria.agent.run",
        attributes={
            "aria.channel": channel,
            "gen_ai.request.model": model,
            "aria.route": route,
        },
    )


def configure_tracing(app: Any) -> dict[str, Any]:
    if _tracing_state["configured"]:
        return status()
    if not settings.otel_enabled:
        _tracing_state["configured"] = True
        return status()
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": settings.otel_service_name}))
        if settings.otel_exporter_otlp_endpoint:
            exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            _tracing_state["exporter_configured"] = True
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()
        _tracing_state["configured"] = True
        logger.info("OpenTelemetry tracing configured")
    except Exception as error:
        _tracing_state["configured"] = True
        logger.warning("OpenTelemetry setup failed (%s)", type(error).__name__)
    return status()


def status() -> dict[str, Any]:
    return {
        "otel_enabled": settings.otel_enabled,
        "instrumentation_configured": bool(_tracing_state["configured"] and settings.otel_enabled),
        "otlp_exporter_configured": bool(_tracing_state["exporter_configured"]),
        "service_name": settings.otel_service_name,
        "prometheus_metrics": "/metrics",
        "audit_trace_ui": "/aria-trace",
    }
