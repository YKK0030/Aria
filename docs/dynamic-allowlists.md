# Dynamic channel allowlists

The authenticated admin API can manage Telegram and WhatsApp chat IDs without
editing `.env`. Updates are written atomically to
`.data/agent-core/allowlists/access-policy-overrides.json`. Agent-core reads them on each
inbound request. The WhatsApp gateway reads the same file for each message and
mounts only this subdirectory read-only; it cannot read the rest of agent data.

```http
GET /admin/allowlists
PUT /admin/allowlists/telegram
DELETE /admin/allowlists/telegram
```

Send `x-admin-api-key` with every request. Example update:

```json
{
  "allowed_chat_ids": ["123456789"],
  "blocked_chat_ids": []
}
```

Telegram IDs are decimal chat IDs represented as strings. WhatsApp IDs must be
exact chat JIDs, such as `15551234567@s.whatsapp.net` or a group JID ending in
`@g.us`. When a managed allowlist is empty, it denies every chat. `DELETE`
removes the managed override and restores the policy-file and environment
fallbacks. Telegram owner commands remain restricted to
`TELEGRAM_ALLOWED_CHAT_IDS`; adding a chat to the ordinary inbound allowlist
does not grant admin controls.

The WhatsApp gateway must be recreated once after deploying the shared-volume
change. Ensure the narrow shared directory exists before Compose creates its
bind mount, so the agent's runtime user owns the writable directory:

```sh
mkdir -p .data/agent-core/allowlists
docker compose up -d --force-recreate agent-core whatsapp-gateway
```
