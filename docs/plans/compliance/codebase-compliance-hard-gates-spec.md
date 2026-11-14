# Spec: Bring codebase to full compliance with hard-enforced CODING_STANDARDS

## Problem Statement

The project now has hard-enforced gates (AGENTS.md, CONTRIBUTING.md, PR template, pre-commit hooks, opencode.json) that require all checks to pass. However, the existing codebase has violations: `make lint` reports 365 ruff errors (mypy and import-linter pass, arch tests pass). The agent must fix all violations so that every gate passes with no exceptions.

## Solution

Systematically fix all lint violations and any structural issues while maintaining behavior. Fix in phases: baseline audit, safe auto-fixes, manual fixes, structural compliance verification, full gate validation. Keep commits small and run gates frequently.

## User Stories

1. As a developer/agent, I want `make lint` to pass with zero errors, so that the lint gate is green.
2. As a developer/agent, I want `make typecheck` to pass, so strict typing is enforced.
3. As a developer/agent, I want `make imports` to pass, so layer rules are enforced.
4. As a developer/agent, I want `make arch-test` to pass, so structural invariants hold.
5. As a developer/agent, I want `make test` and `make test-security` to pass, so behavior is correct.
6. As a developer/agent, I want `make check` and `make ci` to pass, so all gates are green.
7. As a developer/agent, I want pre-commit hooks to pass, so local enforcement works.
8. As a developer/agent, I want all fixes to follow CODING_STANDARDS (one class per file, no utils/helpers, proper layering, etc.).
9. As a developer/agent, I want fixes to be minimal and behavior-preserving where possible.
10. As a developer/agent, I want any necessary refactoring to maintain test coverage and pass all gates.

## Implementation Decisions

- **Baseline first:** Capture full audit of all 365 lint errors, categorized by rule and file (Phase 0)
- **Safe auto-fixes:** Run `ruff check --fix` for safe fixes first; review all changes (Phase 1)
- **Unsafe fixes selectively:** Evaluate unsafe fixes case by case, apply only if safe and behavior-preserving (Phase 1)
- **Manual fixes:** Address remaining errors - type ignores need specific codes (PGH003), imports to TYPE_CHECKING where appropriate (TC003), exception chaining (B904), etc. (Phase 2)
- **Structure:** Verify one-class-per-file, filename matches class name, no utils/helpers, every package has README (Phase 3)
- **Size limits:** Address files >300 lines/functions >30 lines if they exist, refactor by extracting while maintaining SRP and layering (Phase 4)
- **Type/imports:** Ensure mypy --strict and import-linter remain clean (Phases 5-6)
- **Tests:** Run all tests, fix any failures caused by changes (Phase 7)
- **Validation:** Full gate run (Phase 8)
- **No rule disabling:** Don't add broad ignores; use targeted per-file ignores only if they match existing patterns in pyproject.toml
- **Small commits:** Commit per phase/sub-phase
- **Respect existing patterns:** Follow codebase style and patterns

## Testing Decisions

- **External behavior only:** Don't change tests to make broken code pass; fix code to match correct behavior per standards
- **Run gates frequently:** After each phase/sub-phase run relevant gates
- **Full suite at end:** `make test`, `make test-security`, `make check`, `make ci` must all pass
- **Architecture tests:** Must remain green throughout
- **Import-linter:** Must remain green throughout

## Out of Scope

- Changing CODING_STANDARDS.md or gate requirements
- Adding new features
- Major architectural redesigns
- Changing test assertions to weaken requirements

## Further Notes

- Baseline: lint has 365 errors, mypy clean, imports clean, arch tests clean
- Focus on src/ first (production code), then tests if needed
- Some areas have per-file ruff ignores in pyproject.toml - respect them
