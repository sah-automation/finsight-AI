# Architecture Invariant Tests

Tests that enforce architectural invariants not expressible by static tools.

## Test Categories

1. **No env vars outside config** - Only `core/config` may read `os.getenv`/`os.environ`
2. **No vendor imports in domain/application** - Business logic must not import AWS, LLM, or DB libraries
3. **Company ID on all queries** - Every repository/search/cache method requires `company_id`
4. **Money uses Decimal** - Never `float` for monetary values
5. **No hidden dependency construction** - Only `composition`/`adapters` construct clients
6. **One class per file** - File name matches main class name (snake_case)
7. **Every folder has README.md** - Documentation at every level
8. **Size limits** - Files <300 lines, functions <30 lines (warn only)
9. **No env checks in business code** - Use config switches, not `if env == "prod"`

## Running

```bash
# All architecture tests
pytest tests/architecture -v --tb=short -m architecture

# Specific test class
pytest tests/architecture/test_invariants.py::TestNoEnvVarsOutsideConfig -v

# With coverage
pytest tests/architecture --cov=src/finsight --cov-report=term-missing
```

## Adding New Invariants

Add a new test class in `test_invariants.py` following the pattern:
- Mark with `@pytest.mark.architecture`
- Use AST parsing for structural checks
- Fail with clear error messages pointing to file:line
