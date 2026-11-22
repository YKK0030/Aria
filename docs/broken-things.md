# Aria — Broken Things and Workflow Audit

Audit date: 2026-10-19

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

6. **Resolved: agent container root discovery**
   - Root build context now copies `README.md` and `docker-compose.yml`; app import passes in the rebuilt image.

7. **Resolved: command-only startup without Groq**
   - Agno model construction is lazy and occurs only for model-backed requests.
   - Built-in command and fallback smoke checks pass with an empty `GROQ_API_KEY`.

8. **Resolved: dynamic tools in the agent image**
   - Root build context copies `tools/`; Agno tool discovery and agent construction pass in the rebuilt image.

## Verification

- Python source compilation (`python3 -m compileall -q services/agent-core/src`): passed on 2026-10-19.
- WhatsApp gateway TypeScript build (`npm --prefix services/whatsapp-gateway run build`): failed with the 2 errors listed above on 2026-10-19.
- Docker Compose validation (`docker compose config -q`): passed on 2026-10-19 with a temporary empty `.env`; a fresh checkout still needs `.env` because services declare it as `env_file`.
- Valkey 8 container (`valkey-cli ping`): passed on 2026-10-19 (`PONG`).
- Automated tests: none found.
- Agent image build: passed on 2026-10-19 with Agno 2.9.0 and Groq integration installed.
- Agent app import and Agno dynamic-tool construction: passed in the container on 2026-10-19.
- LangGraph rollback graph compilation: passed in the container on 2026-10-19.
- `/help`, `/status`, `/note`, `/todo`, and no-key fallback: passed in the container on 2026-10-19.
- `/help` with Valkey unavailable: passed in the container on 2026-10-19.

## Functional requirement matrix

| Requirement | Status | Evidence |
|---|---|---|
| WhatsApp allowlisting | Blocked | Logic exists, but the gateway TypeScript build fails. |
| Receive selected WhatsApp chats | Blocked | Same gateway build blocker. |
| Send WhatsApp messages | Blocked | Gateway cannot build/start yet. |
| Mark WhatsApp messages read | Blocked | Gateway cannot build/start yet. |
| Forward WhatsApp events to agent | Blocked | Gateway build fails; agent container also crashes at import. |
| Telegram polling and chat filtering | Unverified | Code exists; no live bot credentials/test. |
| Telegram slash commands | Partially verified | Agno `/help`, `/status`, `/note`, and `/todo` passed without Groq in the container. |
| Agno message routing | Partially verified | Built-in command routing, fallback, dynamic tool construction, Valkey-outage behavior, and legacy graph compilation passed in the container. |
| Groq reasoning/model routing | Unverified live | No Groq API key was available for a real model request. |
| Valkey short-term memory | Unverified | Valkey responds to `PING`; client read/write integration remains untested. |
| SQLite long-term graph memory | Passed isolated smoke test | Add/search node succeeded in the agent image. |
| Notes and todos | Passed isolated smoke test | Add note and add todo succeeded. |
| Dynamic repo tools | Passed isolated smoke test | `hello_tool` discovered and accepted by an Agno Agent in Docker. |
| Duplicate-message protection | Unverified | Code exists; no end-to-end delivery test. |
| Admin APIs | Unverified | FastAPI app imports in the rebuilt image; authenticated endpoint flow not tested. |
| Access policy filtering | Unverified | Code/config exists; no route/API integration test. |
| Audit/history persistence | Unverified | Code exists; no end-to-end test. |

## Overall result

The workflow is **not working end to end**. Agent container startup, command-only mode, and dynamic tool packaging now work. Remaining blockers include:

1. Fix the WhatsApp gateway TypeScript build.
2. Provide a Groq key and run a real model request.
3. Resolve fresh-checkout `.env` setup and remaining security/configuration findings.

WhatsApp → agent → reply remains unverified while the gateway build fails.

## Tomorrow checklist

- [ ] Fix the two TypeScript build errors.
- [ ] Protect or remove `/allowlist`.
- [ ] Decide whether Compose should require `.env` or provide safe defaults.
- [ ] Generate and review `package-lock.json`.
- [ ] Fix the README links.
- [ ] Add one small smoke test for gateway build/configuration.
