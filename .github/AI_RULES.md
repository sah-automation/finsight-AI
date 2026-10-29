# AI Agent Rules - MANDATORY ENFORCEMENT

This file ensures ALL AI coding agents follow the project's strict standards.

## MANDATORY READING (in order)
1. AGENTS.md - Contains MANDATORY GATES (NON-NEGOTIABLE)
2. CODING_STANDARDS.md - Complete coding standards
3. CONTRIBUTING.md - Checklist and workflow

## GATES THAT MUST PASS (NO EXCEPTIONS)
```bash
make lint        # ruff
make typecheck   # mypy --strict
make imports     # import-linter
make arch-test   # architecture invariants
make test        # unit + contract + arch + switches
make test-security
```

## CRITICAL CONSTRAINTS
- **One class per file** - filename must match class name in snake_case
- **Strict typing** - mypy --strict, zero errors
- **Import rules** - all import-linter contracts KEPT
- **Layer isolation** - domain pure, no vendors in domain/app
- **Company isolation** - company_id on all repo/search/cache
- **Money** - Decimal only
- **DI only** - constructor injection, no hidden deps
- **No utils/helpers** - name by purpose
- **No env in business logic** - only core/config

## WORKFLOW
1. Read rules before starting
2. Plan changes by layer
3. Make minimal changes
4. Run ALL gates
5. Fix ALL failures
6. Only then report completion

**VIOLATING THESE RULES IS NOT ALLOWED.**
