# Phase 06 — Security and approvals

## Includes

- Authenticate channel ingress.
- Authenticate FastMCP clients.
- Scope Attic namespace to authenticated user.
- Require approval for send, delete, spend, account, and infrastructure tools.
- Do not log secrets or raw content by default.
- Add tool call limits and timeouts.

## Behavior

Read-only tools can run automatically. Sensitive tools pause for confirmation.

## Verification

- Cross-user memory access fails.
- Sensitive tool without approval pauses or fails safely.
- Invalid credentials fail.
- Secret values do not appear in logs.

## Exit gate

Every external action has authentication, authorization, and failure handling.
