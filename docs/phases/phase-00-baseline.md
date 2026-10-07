# Phase 00 — Baseline and contracts

## Includes

- Record current WhatsApp, Telegram, Redis, SQLite, and tool behavior.
- Keep current LangGraph path as rollback until Agno passes.
- Define `user_id`, `session_id`, channel ID, and Attic namespace.
- Define approval-required actions.
- Capture current known blockers in `docs/broken-things.md`.

## Behavior

No user-visible behavior changes.

## Verification

- Python compilation passes.
- Existing command smoke checks pass.
- WhatsApp build result is recorded.
- Docker Compose validation result is recorded.

## Exit gate

Contracts are written and rollback path remains runnable.
