# ADR-0001: Enforce coding standards with tooling and architecture tests

## Status

Accepted

## Context

`CODING_STANDARDS.md` defines rules that are easy to state and easy to break:
layer import direction, no vendor imports in `domain`/`application`, no
environment reads outside `core/config`, `company_id` on every data method,
`Decimal` for money, one main class per file, READMEs in every folder, and both
paths of every config switch. The repository had no automated gate, so these
rules relied entirely on review.

Some rules are expressible by static analysis (import graph, types, style).
Others need to inspect source structure (AST) or behaviour (switch tests). A
few are subjective and must stay in review.

## Decision

Split enforcement into three layers:

1. **Static tools** run in pre-commit and CI:
   `ruff`, `mypy --strict`, `lint-imports`, `vulture`, `detect-secrets`.
2. **Architecture invariant tests** in `tests/architecture/` parse the source
   with `ast` and fail on structural violations that static tools cannot see.
3. **Switch path tests** in `tests/unit/switches/`, with a meta-test that fails
   when a `SwitchesConfig` field has no test file or no ON/OFF test.

`tests/architecture/` is added to the test layout in `CODING_STANDARDS.md`
section 3 and `tests/README.md`. Subjective rules (single responsibility, SOLID
intent, "small boring code") remain review-only and are covered by the section
17 checklist.

The import contracts live in `pyproject.toml` under `[tool.importlinter]` as the
single source of truth; the legacy `.importlinter` file was removed to avoid two
diverging configurations.

## Consequences

- Layer and vendor-import violations fail in seconds instead of at review time.
- An empty `domain`/`application` is only weakly protected; the AST tests skip
  checks whose target code does not exist yet. Each test must be revisited when
  the corresponding module is implemented (noted in its docstring or skip).
- The file/class naming test has a small allow-list for pre-existing exception
  modules (`errors.py`, `types.py`, `models.py`, `loader.py`); new files must
  follow the rule.
- The switch test files currently skip until their features exist. The
  meta-test keeps the coverage requirement visible and fails if a switch is
  added without a test file.
- Coverage is measured but not yet enforced; the ratchet is planned in
  `docs/plans/quality-standards-enforcement.md`.
