# Reminders and scheduled jobs

Aria supports one-time, daily, and weekly reminders for Telegram, WhatsApp,
Slack, and Discord chats. Use the chat where the reminder should arrive:

- “Remind me tomorrow at 9 AM to call home.”
- “List my reminders.”
- “Cancel my weekly reminder to water the plants.”

The model tools create, list, and cancel reminders scoped to the current
channel and chat. Each reminder is persisted as a JSON record under
`.data/agent-core/reminders/`; it is not placed in Redis or Attic. Timestamps
are stored in UTC. Web and CLI sessions cannot receive push notifications, so
Aria does not create reminders from those channels.

The scheduler checks for due reminders every 10 seconds and sends them through
the configured channel adapter. A failed send remains due for retry. One-time
reminders become completed after delivery; recurring reminders advance from
their scheduled time and skip missed intervals after downtime.

Admin API, with `x-admin-api-key`:

```text
GET    /admin/reminders?active_only=true
POST   /admin/reminders
DELETE /admin/reminders/{reminder_id}
GET    /admin/scheduler/jobs
```

`POST /admin/reminders` accepts `channel`, `chat_id`, `text`, `run_at` (ISO
8601 timestamp with timezone), and `recurrence` (`none`, `daily`, or `weekly`).
The jobs endpoint includes the active reminder dispatch loop alongside the
internal daily maintenance jobs.
