# Aria delivery phases

Phases are ordered. Each phase has one owner, one outcome, and one exit gate.

Current phase: **04 — Channel adapters** (WhatsApp live smoke pending pairing and allowlist; Telegram deferred by user). Phases 00, 01, 02, and 03 are complete. Phase 02 passed recall-quality and SQLite backup/restore checks on 2026-10-19. Groq remains available via `MODEL_PROVIDER=groq`.

| Phase | Outcome |
|---|---|
| [00](phase-00-baseline.md) | Baseline and contracts locked |
| [01](phase-01-agno-core.md) | Agno owns agent execution |
| [02](phase-02-memory.md) | Valkey, SQLite, and Attic ownership works |
| [03](phase-03-tools.md) | Tools are easy to add and remove |
| [04](phase-04-channels.md) | WhatsApp and Telegram use one runtime |
| [05](phase-05-fastmcp.md) | ChatGPT can connect through MCP |
| [06](phase-06-security.md) | Approvals and isolation protect actions |
| [07](phase-07-verification.md) | Tests prove critical workflows |
| [08](phase-08-deployment.md) | Docker deployment is repeatable |
| [09](phase-09-production.md) | Production operations are safe |

Do not add a later-phase feature early unless it unblocks the current exit
gate.
