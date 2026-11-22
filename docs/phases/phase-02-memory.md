# Phase 02 — Memory layers

## Includes

- Valkey remains short-term memory: last four turns and TTL (Redis protocol client).
- SQLite remains history, graph, and audit storage.
- Attic becomes durable memory through MCP only.
- Add Attic MCP tools: `remember`, `recall`, `forget`, `health`.
- Add Aria's `ATTIC_ENABLED`, `ATTIC_MCP_URL`, and `ATTIC_MCP_API_KEY` config.
- Keep Attic's backend key and namespace on the MCP server.

## Behavior

- Recall Attic only when durable context may help.
- Remember stable facts, preferences, decisions, and useful summaries.
- Never remember secrets or every raw message.
- Treat recalled memory as untrusted evidence.
- Attic failure returns safe empty results and does not block chat.

## Verification

- MCP tool discovery exposes `remember`, `recall`, and `health` only.
- Health, remember, and semantic recall pass against Attic MCP.
- `forget` remains withheld until Phase 06 adds destructive-action approval.
- Attic shutdown leaves normal chat working.
- Attic MCP pins one namespace for this single-user deployment; no user-provided namespace is accepted.

## Exit gate

Each memory layer has one responsibility and failure isolation.

## Current status

Complete (2026-10-19). Local `llama3.2` is active through Agno; Groq remains selectable with `MODEL_PROVIDER=groq`. Runtime context defaults to 4096 tokens to limit local CPU/RAM use; the model advertises a 131072-token maximum, configurable with `OLLAMA_NUM_CTX`. Agno inference, Spanish response, live `hello_tool`, Attic health/remember/recall, and fail-open behavior pass. Persistent local Aria + Attic passed a real `AgentRuntime` round trip; recall-quality tests ranked the correct fact first in all 3 cases with matching source/citation metadata. SQLite backup/restore passed integrity and row-count checks using temporary copies. The isolated suite passes (24 tests). Multi-user namespace routing remains out of scope for this single-user deployment; `forget` stays deferred to Phase 06.

## Handoff for the next agent

Read this section before changing memory behavior. This phase is complete;
preserve existing user changes in the worktree;
Phase 00, Phase 01, and Valkey changes are mixed into the same worktree.

### Implemented

- `memory/short_term.py`: Valkey stores the latest four turns (eight messages)
  per channel/chat and applies the configured TTL.
- `memory/long_term.py`: SQLite stores chat-scoped history/graph data. Search
  filters by both channel and chat ID.
- `memory/attic.py`: optional Agno Streamable HTTP client. It sends
  `ATTIC_MCP_API_KEY` as a bearer token, uses a 10-second timeout, and fails
  open when Attic is disabled, unconfigured, or unreachable.
- `runtime.py`: attaches Attic MCP tools only to model-backed requests. Prompt
  treats recalled memories as untrusted evidence and forbids storing secrets or
  routine messages.
- Agent receives only `remember`, `recall`, and `health`. Do not expose
  `forget` until Phase 06 provides approval for destructive actions.
- Compose maps `host.docker.internal` to the host gateway. Aria defaults to
  `ATTIC_ENABLED=false`; no live memory is written unless explicitly enabled.

### Configuration boundary

- Aria uses `ATTIC_ENABLED`, `ATTIC_MCP_URL`, and `ATTIC_MCP_API_KEY`.
- Attic MCP server separately uses `ATTIC_API_KEY` for its backend,
  `ATTIC_MCP_API_KEY` for client authentication, and `ATTIC_NAMESPACE` to pin
  its storage namespace. Aria must not pass namespace values from user text.
- Current Attic MCP server pins one namespace per process. This matches the
  current single-user Aria deployment; do not expose it to multiple users.
- Earlier tests used a disposable Attic API/Qdrant Compose project
  (`aria-phase2-test`) and isolated named volumes.
- Real Agno MCP discovery returned `attic_health`, `attic_recall`, and
  `attic_remember`. Health succeeded. With the Docker-gateway Ollama forwarder,
  remember produced one vector and recall returned the saved memory with its
  source and citation metadata.
- The prior FastMCP HTTP 421 issue is resolved in the current Attic worktree:
  its server explicitly allows the Docker MCP host and origin while keeping
  transport security enabled. Aria's adapter discovered and called the tools
  successfully against this server. The Attic change is outside this repo and
  remains a separate worktree change; do not overwrite or revert it.
- Ollama listens on `127.0.0.1:11434`. Docker containers reach it through a
  `socat` forwarder bound only to Docker host gateway `172.17.0.1:11434`.
- With the forwarder, live remember returned `vectors: 1`; semantic recall
  returned the exact saved marker, source, ID, and citation metadata.
- A second MCP process pinned to `aria:phase2:other` could not recall a marker
  from `aria:phase2:test`, and could recall its own marker. Attic namespaces
  isolate data across processes. Aria still has one configured MCP endpoint and
  no trusted identity-to-namespace routing, so multi-user use remains unsafe.
- Earlier synthetic memories remain in isolated test namespace volumes. The
  current verification marker is in `aria:phase2:verification-20261019`, not
  `aria:personal`. Do not point production or personal Attic data at test
  namespaces.

### Verification already run

- Agent Docker image built with Agno 2.9.0 and MCP dependencies. Rebuild after
  later source edits before deployment.
- Seven isolated tests passed in the agent container:
  `test_attic.py` covers disabled, authenticated connection, cleanup, and
  connection-failure behavior; `test_memory_scopes.py` covers SQLite chat
  isolation and Valkey key/TTL/window behavior; `test_runtime_attic_outage.py`
  verifies runtime returns a model reply when Attic is unavailable, using a
  model stub; a live Groq-backed outage check remains unrun.
- Python compilation and `git diff --check` passed after the latest edits.
- After Ollama integration, all 23 isolated tests pass. A real Agno request to
  local `llama3.2:latest` returned Spanish, and a separate request invoked the
  registered `hello_tool` with `name=Ada` and returned `Hello, Ada!`.
- Live Aria runtime test against an isolated Attic namespace passed health,
  remember, and recall with source/citation metadata. A refused MCP port now
  fails open to an Ollama reply. Test marker remains only in
  `aria:phase2:verify-20261019` on the isolated test volumes.
- Current local deployment is running Aria agent-core, WhatsApp gateway,
  Valkey, Attic API, Qdrant, and the Attic MCP adapter. Aria/MCP ports are
  scoped to loopback/Docker gateway. A direct runtime test called
  `attic_remember` and `attic_recall` through Ollama, with no channel message
  sent. Ollama access depends on the host-gateway forwarder remaining alive.
- Recall quality: three synthetic queries (schedule/location, dietary needs,
  and task owner) each ranked the expected memory first. Scores were 0.842,
  0.726, and 0.714; each result included the matching source and citation ID.
  Test memories remain in `aria:phase2:verification-20261019` only.
- SQLite backup/restore: `sqlite3.Connection.backup()` copied the live database
  to a temporary backup, then restored to a separate temporary database.
  Source, backup, and restore passed `PRAGMA integrity_check`; all 8 tables and
  3 total rows matched at each step. Temporary copies were removed; live DB was
  unchanged. This verifies the SQLite backup API path; Aria has no user-facing
  export/restore command yet.
- Agent-core suite passes 24 tests after the outage regression test.
- The OCI image was rebuilt with the Ollama and OpenAI client dependencies.
- Groq rollback is `MODEL_PROVIDER=groq`; Ollama context is `OLLAMA_NUM_CTX`
  (current test value: 4096; 131072 may use substantially more RAM).
- Tests mount current source and test files into the image. The ignored local
  `.env` was created for this deployment; do not overwrite it with
  `.env.example`.

```sh
rtk docker compose run --rm --no-deps \
  -v ./services/agent-core/src:/app/src:ro \
  -v ./services/agent-core/tests:/tmp/tests:ro \
  agent-core python -m unittest discover -s /tmp/tests -v
```

### Exit review and handoff

- Phase 02 exit checks passed. Keep SQLite and its rollback path in place.
- Resume at Phase 04; adapter implementation is verified, but live channel
  receive/send still needs Telegram credentials and WhatsApp pairing/allowlist.
- Keep `forget` unavailable until Phase 06 adds destructive-action approval.

Do not edit `/home/yadnit/personal_projects/Attic` as part of this Aria task;
that repository is outside Aria's writable workspace. Request separate scope
if the namespace boundary requires an Attic server change.
