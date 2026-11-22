# Code Review Guide

When reviewing code (yours or user's):

## Checklist
- [ ] **Correctness**: Does it solve the stated problem?
- [ ] **Tests**: New tests for new behavior, existing tests pass
- [ ] **Style**: Matches project conventions (lint, formatting)
- [ ] **Types**: Type annotations present and correct
- [ ] **Security**: No secrets, injection risks, path traversal
- [ ] **Performance**: No obvious N+1, unbounded loops, memory leaks
- [ ] **Maintainability**: Clear naming, single responsibility, low coupling

## Review Format
```
## Summary
Brief description of changes

## Concerns (blocking)
- Specific issue with file:line reference

## Suggestions (non-blocking)
- Improvement idea

## Approved
Yes/No - with conditions if any
```

## For Aria Source Changes
- Use `propose_code_change` tool
- Only unprotected `agent_core/**/*.py` files
- Never: prompts, config, policy, tools, memory, storage, databases