# Copilot/Agent Instructions (MANDATORY)

You MUST follow ALL rules in:
- AGENTS.md (MANDATORY GATES)
- CODING_STANDARDS.md (complete standards)
- CONTRIBUTING.md (checklist)

BEFORE completing ANY task:
1. Run: make lint && make typecheck && make imports && make arch-test && make test && make test-security
2. If ANY fail, FIX THEM. Do not claim done.
3. Verify: one class per file, strict typing, import rules, no vendor in domain/app, company_id on queries, Decimal for money.

NO EXCEPTIONS. These are enforced by architecture tests and import-linter.
