# Refactoring Guide

When user asks to refactor or improve code:

## Principles
- **Behavior preservation**: All existing tests must pass
- **Incremental**: Small, reviewable steps
- **Measurable**: Define what "better" means (complexity, duplication, performance)

## Process
1. **Analyze**: Current structure, dependencies, test coverage
2. **Identify**: Code smells (duplication, long functions, tight coupling)
3. **Plan**: Target architecture, intermediate steps
4. **Execute**: One refactoring at a time, run tests after each
5. **Verify**: Full test suite, performance benchmarks if applicable

## Common Patterns
- Extract function/class for duplication
- Introduce interfaces for testability
- Replace conditionals with polymorphism
- Centralize configuration/constants
- Improve naming for clarity

## Safety
- Never refactor without tests
- Use `git diff` to verify minimal changes
- Commit each refactoring separately