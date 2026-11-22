# Debugging Guide

When user reports a bug or error:

## 1. Reproduce
- Get exact error message, stack trace, steps to reproduce
- Check if existing tests cover the scenario
- Run the failing case via `workspace_terminal`

## 2. Locate
- Use stack trace to find source location
- Search for related code: `grep` via `workspace_terminal`
- Check recent changes: `git log --oneline -20`

## 3. Hypothesize
- Form 2-3 hypotheses about root cause
- Prioritize by: recent changes, complexity, external deps

## 4. Verify
- Add debug logging or use debugger
- Write minimal reproduction test
- Confirm hypothesis before fixing

## 5. Fix
- Minimal change addressing root cause
- Add regression test
- Run full test suite

## 6. Communicate
- Explain root cause in plain language
- Show the fix with context
- Note any follow-up needed