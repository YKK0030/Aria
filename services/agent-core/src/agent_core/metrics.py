from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable

from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

# Request metrics
http_requests_total = Counter(
    "aria_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "aria_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Agent metrics
agent_runs_total = Counter(
    "aria_agent_runs_total",
    "Total agent runs",
    ["channel", "route", "model", "status"],
)

agent_run_duration_seconds = Histogram(
    "aria_agent_run_duration_seconds",
    "Agent run latency",
    ["channel", "model"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

tool_calls_total = Counter(
    "aria_tool_calls_total",
    "Total tool calls",
    ["tool", "status"],
)

tool_call_duration_seconds = Histogram(
    "aria_tool_call_duration_seconds",
    "Tool call latency",
    ["tool"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Memory metrics
memory_operations_total = Counter(
    "aria_memory_operations_total",
    "Total memory operations",
    ["operation", "layer", "status"],
)

short_term_memory_size = Gauge(
    "aria_short_term_memory_messages",
    "Number of messages in short-term memory",
    ["channel", "chat_id"],
)

long_term_memory_nodes = Gauge(
    "aria_long_term_memory_nodes",
    "Number of nodes in long-term memory",
    ["channel", "chat_id"],
)

# Skill metrics
skill_activations_total = Counter(
    "aria_skill_activations_total",
    "Total skill activations",
    ["skill", "trigger"],
)

skill_scores = Gauge(
    "aria_skill_score",
    "Learned skill preference score",
    ["channel", "chat_id", "skill"],
)

# Consolidation metrics
consolidation_runs_total = Counter(
    "aria_consolidation_runs_total",
    "Total consolidation runs",
    ["status"],
)

consolidation_duration_seconds = Histogram(
    "aria_consolidation_duration_seconds",
    "Consolidation run duration",
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)

consolidation_memories_created = Counter(
    "aria_consolidation_memories_created_total",
    "Memories created during consolidation",
    ["type"],
)

# Webhook metrics
webhook_events_total = Counter(
    "aria_webhook_events_total",
    "Total webhook events received",
    ["channel", "status"],
)

# Model metrics
model_tokens_used = Counter(
    "aria_model_tokens_used_total",
    "Total tokens used",
    ["model", "type"],  # type: prompt/completion
)

model_errors_total = Counter(
    "aria_model_errors_total",
    "Total model errors",
    ["model", "error_type"],
)

# Active connections
active_websockets = Gauge(
    "aria_active_websockets",
    "Active WebSocket connections",
    ["channel"],
)

# Queue depths
task_queue_depth = Gauge(
    "aria_task_queue_depth",
    "Tasks waiting in queue",
    ["queue"],
)


def record_http_request(method: str, endpoint: str, status: int, duration: float) -> None:
    http_requests_total.labels(method=method, endpoint=endpoint, status=str(status)).inc()
    http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)


def record_agent_run(channel: str, route: str, model: str, status: str, duration: float) -> None:
    agent_runs_total.labels(channel=channel, route=route, model=model, status=status).inc()
    agent_run_duration_seconds.labels(channel=channel, model=model).observe(duration)


def record_tool_call(tool: str, status: str, duration: float) -> None:
    tool_calls_total.labels(tool=tool, status=status).inc()
    tool_call_duration_seconds.labels(tool=tool).observe(duration)


def record_memory_op(operation: str, layer: str, status: str) -> None:
    memory_operations_total.labels(operation=operation, layer=layer, status=status).inc()


def record_skill_activation(skill: str, trigger: str) -> None:
    skill_activations_total.labels(skill=skill, trigger=trigger).inc()


def record_skill_score(channel: str, chat_id: str, skill: str, score: float) -> None:
    skill_scores.labels(channel=channel, chat_id=chat_id, skill=skill).set(score)


def record_consolidation(status: str, duration: float, memories: dict[str, int]) -> None:
    consolidation_runs_total.labels(status=status).inc()
    consolidation_duration_seconds.observe(duration)
    for mem_type, count in memories.items():
        consolidation_memories_created.labels(type=mem_type).inc(count)


def record_webhook_event(channel: str, status: str) -> None:
    webhook_events_total.labels(channel=channel, status=status).inc()


def record_model_tokens(model: str, token_type: str, count: int) -> None:
    model_tokens_used.labels(model=model, type=token_type).inc(count)


def record_model_error(model: str, error_type: str) -> None:
    model_errors_total.labels(model=model, error_type=error_type).inc()


def metrics_endpoint() -> Response:
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Decorator for timing async functions
def timed(metric_func: Callable, *labels, **label_kwargs):
    """Decorator to time an async function and record to a histogram."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration = time.perf_counter() - start
                metric_func(*labels, **label_kwargs, duration=duration)
                return result
            except Exception as e:
                duration = time.perf_counter() - start
                metric_func(*labels, **label_kwargs, duration=duration, status="error")
                raise
        return wrapper
    return decorator


def get_metrics_snapshot() -> dict:
    """Return a JSON-serializable snapshot of all registered metrics."""
    import prometheus_client as pc
    registry = pc.REGISTRY
    snapshot = {}
    for metric in registry._collector_to_names:
        pass
    # Simpler: use generate_latest and parse text lines
    from prometheus_client import generate_latest
    data = generate_latest().decode()
    for line in data.splitlines():
        line=line.strip()
        if not line or line.startswith("#"):
            continue
        # format: metric_name{labels} value timestamp
        # We'll parse roughly
        try:
            if "{" in line:
                name_part, rest = line.split("{",1)
                labels_part, value_part = rest.split("}",1)
                labels = {}
                for kv in labels_part.split(","):
                    if "=" in kv:
                        k,v = kv.split("=",1)
                        labels[k]=v.strip('"')
                value = float(value_part.split()[0])
            else:
                name_part, value_part = line.split(" ",1)
                labels = {}
                value = float(value_part.split()[0])
            snapshot.setdefault(name_part, []).append({"labels": labels, "value": value})
        except Exception:
            continue
    return snapshot
