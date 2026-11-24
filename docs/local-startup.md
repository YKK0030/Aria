# Local startup: Aria + Attic

Linux development setup using Ollama, Docker Compose, and the local Attic MCP
server. This guide does not configure Telegram or pair WhatsApp.

## 1. Prepare Aria

From the Aria repo:

```sh
cd /home/yadnit/personal_projects/Aria
cp .env.example .env   # only if .env does not already exist
```

Keep an existing `.env`; do not overwrite local keys. Confirm it has
`MODEL_PROVIDER=ollama`, `OLLAMA_MODEL=llama3.2:latest`, and
`OLLAMA_HOST=http://host.docker.internal:11434`. Pull the model once:

```sh
ollama pull llama3.2
```

Ollama must be running on the host. The current local setup binds Ollama to
loopback and uses this bridge forwarder for Docker containers. In a separate
terminal, run this only if port 11434 on 172.17.0.1 is not already listening;
leave the terminal open:

```sh
rtk socat TCP-LISTEN:11434,bind=172.17.0.1,reuseaddr,fork TCP:127.0.0.1:11434
```

## 2. Start Attic (optional)

Attic is a separate checkout and stack:

```sh
cd /home/yadnit/personal_projects/Attic
docker compose -f docker/docker-compose.yml up -d --build
```

Check the service at <http://localhost:4000/> or <http://localhost:4000/docs>.
The compose default API key is `dev-key` for local development only. Do not
expose this service to an untrusted network.

Aria's MCP adapter is a separate container, not part of either compose file.
Start it using the project setup recorded in `docs/ATTIC_MCP_README.md` in
Aria. For normal personal use, configure the adapter namespace as
`aria:personal`, then set `ATTIC_ENABLED=true` and the matching
`ATTIC_MCP_API_KEY` in Aria's `.env`. Do not reuse the Phase 02 verification
namespace. If an `aria-attic-mcp` container is already running with the
verification namespace, stop/recreate it with the personal namespace before
using personal memory.

## 3. Choose channels and start Aria

Use one launcher command. Server channels start in Docker; if `cli` is selected,
the same command opens the interactive CLI after startup. Voice replaces CLI and
is enabled only with `--voice`.

```sh
cd /home/yadnit/personal_projects/Aria
python3 tools/aria start --channels cli,web,telegram
```

Other examples: `python3 tools/aria start --channels all` starts CLI plus all
configured server channels; `python3 tools/aria start --channels web,telegram`
starts those services without an interactive terminal; add `--voice` to start
the local voice client instead of CLI (web is enabled automatically). The
WhatsApp Compose profile starts only when WhatsApp is selected. Telegram needs a
bot token and allowed chat IDs; WhatsApp requires pairing and a non-empty
`WHATSAPP_ALLOWED_NUMBERS` allowlist.
To approve actions in WhatsApp, also set your private number in
`WHATSAPP_OWNER_NUMBERS`; ordinary allowlisting does not grant owner controls.
Use `/approvals`, then `/approve ID` or `/reject ID` in that private chat.

For Telegram, set both `TELEGRAM_BOT_TOKEN` and your private numeric ID in
`TELEGRAM_ALLOWED_CHAT_IDS`. Only allowlisted chats can talk to Aria; owner
controls (`/review`, `/approve`, `/trace`) are restricted to an allowlisted
private chat. `/review NAME` requires isolated tests to have already run from
the local CLI (`python3 tools/aria tools test NAME`). `/approve NAME` shows the reviewed source and asks for an explicit
confirmation button. Completed CLI, web, and WhatsApp requests send a short
Telegram notification to allowlisted IDs. Use `/trace 30m`, `/trace 2h`, or
`/trace today` for recent activity. `/help` lists commands. Code-patch
application remains CLI-only.

To find your numeric Telegram ID, message `@userinfobot` in Telegram and copy
the ID it returns into `.env` (do not put your bot token in chat). Restart Aria
after updating the token or allowlist.

For browser access, open `http://127.0.0.1:8001/command-center`; chat is at `/`,
trace at `/aria-trace`, dashboard at `/dashboard`, and short-/long-term memory
at `/memory`. Enter the `ADMIN_API_KEY` from your local `.env` to load private operational data. Aria and its
admin endpoints are bound to loopback; Valkey is available only inside Docker.

For direct API use, send an authenticated prompt:

```sh
curl -X POST http://127.0.0.1:8001/chat \
  -H 'content-type: application/json' \
  -H 'x-admin-api-key: YOUR_ADMIN_API_KEY' \
  -d '{"text":"Hello Aria","session_id":"my-session"}'
```

`GET /health` checks service health; `GET /admin/status` reports selected
channels and requires the admin key. Trace records can include conversation text
and tool arguments. The trace page shows operational events and visible outputs,
not private model reasoning.
Tool proposal review and sandbox approval steps are in
[task-tools.md](task-tools.md).

To watch service logs:

```sh
docker compose logs -f agent-core
docker compose logs -f whatsapp-gateway
```

## Stop services

Stop Aria and Attic from their respective repos:

```sh
# Aria
python3 tools/aria stop

# Attic
docker compose -f docker/docker-compose.yml down
```

These commands preserve named volumes. Do not add `-v` unless you intend to
delete persisted local data. Stop the `socat` forwarder with Ctrl-C in its
terminal. Stop the separately launched MCP adapter with
`docker stop aria-attic-mcp` if it is running.
