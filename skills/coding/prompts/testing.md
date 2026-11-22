# Testing Guide

## Test Strategy
- **Unit**: Pure functions, isolated logic (fast, many)
- **Integration**: Component interactions, API contracts (medium)
- **E2E**: Full user flows, critical paths (slow, few)

## When Writing Tests
1. **Name clearly**: `test_<function>_<scenario>_<expected>`
2. **Arrange-Act-Assert**: Clear structure
3. **One assertion per test** (ideally)
4. **Deterministic**: No flaky timeouts, random data
5. **Fast**: Mock external deps, use in-memory DBs

## Running Tests
```bash
# Python (pytest)
pytest tests/ -v --tb=short
pytest tests/test_specific.py::TestClass::test_method -v

# Coverage
pytest --cov=src --cov-report=term-missing

# Typecheck
mypy src/
ruff check src/
```

## Test Data
- Use fixtures for common setups
- Factory functions for complex objects
- Parametrize for multiple inputs

## Debugging Failed Tests
```bash
# Run single test with output
pytest tests/test_x.py::test_y -v -s --tb=long

# Drop into debugger on failure
pytest --pdb
```