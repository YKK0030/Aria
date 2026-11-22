# Aria observability

Aria keeps Prometheus metrics and its existing `/aria-trace` audit view. Agent
Core also writes structured JSON logs to stdout for container log collection.
Logs include event names, request IDs, and—when tracing is active—trace IDs.
They avoid message text and credentials.

## OpenTelemetry

Tracing is off by default. To enable it, set these environment variables for
`agent-core`:

```env
OTEL_ENABLED=true
OTEL_SERVICE_NAME=aria-agent-core
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

The endpoint is an optional OTLP gRPC collector. If it is empty, spans are
created and instrumented but are not exported. Restart the service after
changing settings.

## Inspection

- `/metrics` — Prometheus scrape endpoint.
- `/admin/metrics/json` — authenticated metrics snapshot.
- `/admin/observability` — authenticated instrumentation and exporter status.
- `/aria-trace` — existing audit timeline; records include request/trace IDs
  when available.
- `docker compose logs -f agent-core` — structured JSON request and agent events.

Use `request_id` to follow one HTTP request through logs and audit entries. Use
`trace_id` to correlate exported spans with the collector UI. Telegram and
other background channel events may have a trace ID without an HTTP request ID.
