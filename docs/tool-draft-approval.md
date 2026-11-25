# Generated tool approval

Generated tools stay inactive until the current source passes every isolated test, an independent reviewer approves that same source revision, and the owner confirms installation.

## Local CLI

Run commands from the Aria repository on the computer running Aria. The CLI reads `ADMIN_API_KEY` or `ARIA_ADMIN_KEY` from the process environment or repository `.env`; use `--key` to override it.

```bash
python3 tools/aria tool draft list
python3 tools/aria tool draft test TOOL_NAME
python3 tools/aria tool draft review TOOL_NAME
python3 tools/aria tool draft approve TOOL_NAME
```

The CLI sends test requests to Aria, which runs them in the isolated `tool-test-runner` service. A failed or incomplete suite does not mark the draft tested. Approval asks you to type the tool name before installation. To handle reviewer findings, run `python3 tools/aria tool draft revise TOOL_NAME`, then test the new revision.

## Web and Telegram

Open `/tool-drafts` in Aria’s local web UI to inspect source and edit test cases. Run the suite from the page; the backend sends the draft to the isolated `tool-test-runner` service. Review is enabled only after every case passes. Type the exact tool name to approve and install it. Editing tests invalidates old test and review results.

In the allowlisted private Telegram chat, use `/pending` for the current step. Run the displayed test command on the Aria computer, then use `/review TOOL_NAME`. If changes are requested, use `/revise TOOL_NAME`; after a fresh test and review, `/approve TOOL_NAME` displays the source and asks for explicit confirmation.

Sensitive-action approvals are a separate queue. Approving one records authorization for that action; it does not install a tool or execute the action by itself.
