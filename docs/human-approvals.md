# Human approvals

Aria can queue a sensitive action for an explicit owner decision. The model tool
`request_human_approval` records the action name, a short summary, exact details,
requesting channel, and timestamps in `.data/agent-core/approvals/`. Requests
expire after 24 hours. They are separate from conversation memory and are not
stored in Redis or Attic.

The owner can review pending requests in the allowlisted Telegram direct chat
with `/approvals`, then approve or reject with the inline buttons. WhatsApp
owners can use `/approvals [page]`, `/approve ID`, and `/reject ID` in a private
chat after setting `WHATSAPP_OWNER_NUMBERS`; ordinary chat allowlisting and
group access do not grant owner controls. IDs shown in WhatsApp can be entered
using their eight-character prefix.

The `request_outbound_message_approval` tool stores the exact Telegram or
WhatsApp destination and message. Approval sends that bound message once and
records success or failure; a failed delivery is not retried automatically.
Other generic approval requests remain decision-only until an action-specific
executor is added. Authenticated admin clients can still list, inspect, create,
and decide requests through `/admin/approvals`; every endpoint requires
`x-admin-api-key`, and message approvals use the same execution path.

Generic approval records remain decision-only. They do not execute commands,
modify files, or resume paused agent runs. New executable actions must bind
their exact parameters to the request and recheck the one-time, unexpired
decision at execution time; model-supplied free-form details never become
executable code.
