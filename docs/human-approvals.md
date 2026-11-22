# Human approvals

Aria can queue a sensitive action for an explicit owner decision. The model tool
`request_human_approval` records the action name, a short summary, exact details,
requesting channel, and timestamps in `.data/agent-core/approvals/`. Requests
expire after 24 hours. They are separate from conversation memory and are not
stored in Redis or Attic.

The owner can review pending requests in the allowlisted Telegram direct chat
with `/approvals`, then approve or reject with the inline buttons. Authenticated
admin clients can list, inspect, create, and decide requests through
`/admin/approvals`; every endpoint requires `x-admin-api-key`. Decisions are
one-time, persisted, and written to the audit log.

An approval record is an authorization decision only. It does not execute a
command, send a message, modify files, or resume a paused agent run. A sensitive
action integration must check the matching approved request before performing
its operation. This keeps approval separate from execution and prevents a
generic model supplied payload from becoming executable code.
