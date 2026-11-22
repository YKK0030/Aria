# Phase 00 — Baseline and contracts

## Includes

- Record current WhatsApp, Telegram, Valkey, SQLite, and tool behavior in `docs/broken-things.md`.
- Keep current LangGraph path as rollback until Agno passes its Phase 01 exit gate.
- Lock identity and action contracts below before changing runtime ownership.
- Capture current known blockers in `docs/broken-things.md`.

## Contracts

- `channel_id` identifies the transport (`whatsapp` or `telegram`).
- Current conversation scope is `(channel_id, chat_id)`. `sender_id` identifies the actor in that chat; group messages must not treat the group as the sender.
- Future `user_id` means the authenticated person, normalized across channels only when a trusted identity mapping exists. Never infer cross-channel identity from display names.
- `session_id` identifies one conversation scope and remains stable across messages. Until a shared identity service exists, derive it from `channel_id` and `chat_id`.
- Attic namespace is server-derived from authenticated `user_id`; clients and message text cannot choose it. Without a trusted user mapping, keep memory isolated to the channel conversation.
- Require explicit human approval before sending a manually initiated external message, deleting data, spending money, changing accounts, or operating infrastructure. Inbound-triggered replies remain subject to channel allowlists and Phase 06 policy.
- Current executable agent path is LangGraph. Architecture documents describe Agno as the target; keep LangGraph runnable until Phase 01 passes.

## Behavior

No user-visible behavior changes.

## Verification

- Python compilation passes.
- Existing command smoke checks pass.
- WhatsApp build result is recorded.
- Docker Compose validation result is recorded.

## Exit gate

Contracts are written, current behavior and blockers are recorded, baseline checks are recorded, and LangGraph rollback path remains available for rollback.

## Current status

Complete. Contracts, baseline behavior, and known blockers are recorded. Python compilation passes; the earlier container audit passed `/help`; current gateway and fresh-checkout Compose limitations are recorded. LangGraph source remains available for rollback through Phase 01. See `docs/broken-things.md` for the current local smoke-check dependency limitation.
