# Task-specific tools

Aria can draft reusable Python tools during local CLI and authenticated web/API
sessions. Drafts are stored as proposals; their code is not run or registered
until the guarded workflow below is completed.

## Inventory and management

Ask Aria “what tools are available?” to list registered tools, or “list pending
tool drafts” to inspect uninstalled drafts. In voice mode, “test them” runs the
isolated sandbox tests for all pending drafts; “test tool NAME” targets one
draft. Testing never installs a tool.

Voice proposals live as JSON files in `.data/agent-core/tool-proposals/`, which
Docker bind-mounts from the Aria repository. They are not stored in Redis or
Attic. Redis holds short-term chat history; Attic holds long-term user memory.

Aria may delete an explicitly named uninstalled draft when asked. If multiple
drafts share that name, she asks before deleting all matches. Installed tools
cannot be deleted through voice. Remove an installed generated tool only from
the authenticated CLI, which requires typing an exact confirmation:

```sh
python3 tools/aria tools active
python3 tools/aria tools delete TOOL_NAME
```

To update an installed generated tool, ask Aria to draft an update. The update
keeps the tool's name and leaves the installed version untouched until it passes
the same sandbox, independent review, and explicit CLI approval flow below.
Built-in project tools are not eligible for this dynamic update/delete path.

## Automatic review and owner approval

```sh
python3 tools/aria tools list
python3 tools/aria tools review TOOL_NAME
```

`review` automatically runs the proposal's declared tests in a one-shot Docker
sandbox with no network, a read-only root filesystem, no Linux capabilities,
and CPU/memory/process limits. A separate, tool-less reviewer agent inspects the
source and test results. If review finds blockers, Aria receives that feedback
and may create up to two new proposal revisions; each revision must pass the
sandbox and a fresh review. If review passes, the CLI displays the final source
and asks you to type an approval phrase. No tool is installed before that
confirmation. Ambiguous or unavailable reviews fail closed.

You can also run `python3 tools/aria tools approve TOOL_NAME` later for a
proposal already marked `reviewed`; it shows the source and asks for the same
typed confirmation. `tools test` remains available as a manual sandbox-only
check, but it does not satisfy the reviewer gate.

In local voice mode, say “approve NAME”. Aria runs sandbox tests if the draft is
still pending, then runs independent review. If both pass, say “confirm approve
NAME” to install. Voice is not speaker-authenticated; use this only in a trusted,
private environment. The CLI remains safer when other people can access the mic.

After approval, Aria stores the tool under `.data/agent-core/generated-tools`;
the registry discovers it on the next agent request, without a restart, and it
survives container rebuilds. The tool is offered to Aria's model as a callable
Agno tool; Aria decides when it is relevant and invokes it with validated
arguments.

The authenticated API exposes proposal creation/list/detail and protected
review/approval endpoints. Send `x-admin-api-key` with each request. CLI review
is the recommended path because it runs the sandbox before invoking the reviewer.

Treat reviewer approval as guidance, not a security proof. The sandbox only
checks declared behavior; after your approval, code executes inside Aria's agent
container with its runtime permissions. Read the displayed source before
approval. Tool creation is unavailable from Telegram and WhatsApp; approved
tools can still be used by those channels.

## Aria runtime self-maintenance

Aria can inspect ordinary agent-core Python files and submit a unified-diff
proposal with `propose_code_change` from CLI, web, or her allowlisted Telegram
chat. Configuration, policy, tools, prompts, memory, storage, and databases are
protected. Proposals are saved in the persistent agent data volume, not Attic.

```sh
python3 tools/aria code list
python3 tools/aria code review PROPOSAL_ID
python3 tools/aria code apply PROPOSAL_ID
```

`code review` runs a separate reviewer with no tools. The reviewer sees an
untested patch and can reject it; it is not a security proof. If it passes, the
CLI prints the complete patch and requires `apply PROPOSAL_ID`. It verifies the
reviewed digest and `git apply --check`, applies the patch on the host, runs the
agent-core test suite in a temporary container, then rebuilds/restarts Aria only
if tests pass. Aria never receives direct host-workspace write access. The owner
still reviews and explicitly approves every patch.

If you cancel at the confirmation prompt, the proposal remains reviewed; run
`code apply PROPOSAL_ID` later to see it again and approve it without rerunning
the reviewer.
