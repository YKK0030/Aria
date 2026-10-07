# Aria — Broken Things and Workflow Audit

Audit date: 2026-10-05

## Findings

1. **Gateway build fails**
   - File: `services/whatsapp-gateway/src/whatsapp.ts`
   - Lines: 116, 118
   - TypeScript rejects nullable `pushName` and optional `isJidGroup()` values.

2. **Docker Compose fails from a fresh checkout**
   - `docker compose up` fails when `.env` has not been created.
   - The setup docs mention copying `.env.example`, but the command is not self-starting.

3. **Unauthenticated allowlist endpoint**
   - Endpoint: `GET /allowlist`
   - Exposes configured phone numbers and group IDs without an API key.

4. **Dependencies are not reproducible**
   - No `package-lock.json` exists for the WhatsApp gateway.
   - Dependency resolution can change between installs.
   - Installation reported two high-severity advisories; run a lockfile-backed audit after fixing reproducibility.

5. **README contains broken links**
   - The dynamic tools links point to `D:\tp\tools\...` instead of repository-relative paths.

6. **Agent container crashes during startup**
   - The Dockerfile does not copy the root `README.md` and `docker-compose.yml`.
   - `_find_repo_root()` therefore raises `IndexError` before FastAPI starts.

7. **Agent cannot start without a Groq key**
   - `AgentOrchestrator` constructs `ChatGroq` at import time.
   - An empty `GROQ_API_KEY` raises `groq.GroqError`, contradicting the documented
     fallback behavior for built-in commands.

8. **Dynamic tools are absent in the agent image**
   - The Dockerfile copies only `pyproject.toml` and `src`.
   - The repo-root `tools/` directory is not copied or mounted, so dynamic tools
     work locally but not in Docker.

## Verification

- Python source compilation: passed.
- WhatsApp gateway TypeScript build: failed with 2 errors.
- Docker Compose validation: failed because `.env` is missing.
- Automated tests: none found.

## Functional requirement matrix

| Requirement | Status | Evidence |
|---|---|---|
| WhatsApp allowlisting | Blocked | Logic exists, but the gateway TypeScript build fails. |
| Receive selected WhatsApp chats | Blocked | Same gateway build blocker. |
| Send WhatsApp messages | Blocked | Gateway cannot build/start yet. |
| Mark WhatsApp messages read | Blocked | Gateway cannot build/start yet. |
| Forward WhatsApp events to agent | Blocked | Gateway build fails; agent container also crashes at import. |
| Telegram polling and chat filtering | Unverified | Code exists; no live bot credentials/test. |
| Telegram slash commands | Partially verified | Graph `/help` smoke test passed with a valid Groq key. |
| LangGraph message routing | Partially verified | Graph compiled and command route passed in the container. |
| Groq reasoning/model routing | Blocked without key; unverified live | Empty key crashes startup; real API call not tested. |
| Redis short-term memory | Unverified | Code exists; no Redis-backed integration test run. |
| SQLite long-term graph memory | Passed isolated smoke test | Add/search node succeeded in the agent image. |
| Notes and todos | Passed isolated smoke test | Add note and add todo succeeded. |
| Dynamic repo tools | Works locally, broken in Docker | Docker image does not contain or mount `tools/`. |
| Duplicate-message protection | Unverified | Code exists; no end-to-end delivery test. |
| Admin APIs | Blocked in Docker | Agent startup fails before routes are available. |
| Access policy filtering | Unverified | Code/config exists; no route/API integration test. |
| Audit/history persistence | Unverified | Code exists; no end-to-end test. |

## Overall result

The workflow is **not working end to end**. The first hard blockers are:

1. Fix the WhatsApp gateway TypeScript build.
2. Fix agent Docker repo-root discovery.
3. Make Groq initialization optional so command-only mode can start without a key.
4. Copy or mount `tools/` in the agent container.

Until those are fixed, WhatsApp → agent → reply cannot be considered functional.

## Tomorrow checklist

- [ ] Fix the two TypeScript build errors.
- [ ] Protect or remove `/allowlist`.
- [ ] Decide whether Compose should require `.env` or provide safe defaults.
- [ ] Generate and review `package-lock.json`.
- [ ] Fix the README links.
- [ ] Add one small smoke test for gateway build/configuration.
