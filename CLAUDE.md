# CLAUDE.md - MANDATORY COMPLIANCE

This project enforces strict coding standards. You MUST comply with:
- AGENTS.md (MANDATORY GATES - NON-NEGOTIABLE)
- CODING_STANDARDS.md
- CONTRIBUTING.md

## Required Gates (RUN BEFORE DECLARING DONE)
```bash
make preflight && make test-security
```

## Critical Rules
- One main class per file, filename matches class name (snake_case)
- mypy --strict must pass with zero errors
- import-linter contracts must all be KEPT
- Domain/application: no vendor imports, no vendor branching, no env vars, no hidden deps
- Every repo/search/cache method must take company_id
- Money = Decimal only, never float
- Constructor injection only
- No utils.py/helpers.py
- Every package needs README.md

VIOLATIONS ARE NOT ACCEPTABLE. FIX THEM IMMEDIATELY.
