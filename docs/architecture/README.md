# Aria architecture diagrams

- [System map](aria-system-map.svg) — high-level component map and request path.
- [Feature architecture](aria-feature-architecture.svg) — low-level route, module, state, and workflow map for the current features.
- [Runtime flow](aria-runtime-flow.svg) — top-to-bottom live request path, with background jobs in a separate lane.

Open a diagram in a browser or image viewer. The feature map is a large,
scalable poster; zoom in to inspect the route and module labels.

The runtime flow distinguishes automatically loaded short-term turns in
Valkey from on-demand local SQLite search (`graph_memory_search`) and optional
Attic MCP calls. Attic is the separate durable-memory service: when enabled,
Aria provides `remember`, `recall`, and `health` tools to the model. The model
can call `recall` when it needs relevant durable memories; results return to
that agent run. Attic availability and its API key are configured in the agent
environment.
