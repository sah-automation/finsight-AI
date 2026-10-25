# Tests

Test organization mirroring src structure.

**Structure:**
- `unit/` - mirrors src/ folder by folder, fast, fakes for ports
- `unit/switches/` - one test file per config switch; must cover ON and OFF
- `integration/` - real adapters, real services (localstack, test DB)
- `golden/` - 100+ question set, runs on pilot and standard config
- `contract/` - one shared test per port, run against every adapter
- `architecture/` - AST-based invariant tests for rules static tools cannot express

**Enforcement gates:**
- `ruff` - style, imports, security lint rules
- `mypy --strict` - type correctness in `src/`
- `lint-imports` - layer and vendor-import contracts from `pyproject.toml`
- `vulture` - dead code
- `detect-secrets` - no committed credentials
- `pytest tests/architecture` - AST invariants (company_id, Decimal money, env reads, naming)
- `pytest tests/unit/switches` - every switch has ON and OFF tests

**Rules:**
- Every new class ships with tests in same PR
- Unit: no network, fakes for ports
- Contract: proves Liskov substitution
- Both paths: each switch tested on and off
- Golden: same answers on pilot and standard, score drop blocks release
- Security: role table, cache key, company filter tests
- Failure: kill job halfway, duplicate message, block provider
- 85%+ coverage on domain and application
- Deterministic: no real model calls in unit tests