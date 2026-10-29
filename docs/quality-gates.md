# Advanced quality gates: property, mutation, and security scanning

Baseline established by issue #80. These gates strengthen test strength and
security coverage without weakening the fast PR path.

## Property-based tests

- Location: `tests/property/` (aliases: `tests/properties/`, `tests/property_based/`,
  `tests/hypothesis/`, `tests/unit/property/`, `tests/unit/properties/`).
- Marker: `property`.
- Coverage: parsers, config handling, money calculations, and cache keys.
- Ownership: application/domain maintainers.
- Run frequency: fast PR feedback (Python test suite) and the scheduled advanced gate.
- Unstable or heavy examples are scoped to the scheduled advanced gate; the
  fast PR path runs deterministic property examples only.

## Mutation testing

- Scope: `src/finsight/domain` and `src/finsight/application`.
- Configuration: `[tool.mutmut]` in `pyproject.toml`.
- Makefile: `make mutation`, `make mutation-report`.
- Workflow: `.github/workflows/mutation.yml` (scheduled/manual).
- Ownership: domain/application maintainers and quality owner.
- Run frequency: scheduled weekly or manual for PRs labeled appropriately.
- Mutants are reported, not turned into noisy PR blockers unless explicitly opted in.

## Baseline static security scanning

- Source code: Bandit (`bandit -r src/finsight -c pyproject.toml`).
- Dependencies: pip-audit (existing dependency audit).
- Containers and files: Trivy baseline scan.
- Infrastructure: Trivy config/infra scan baseline.
- Config: `.semgrep.yml`, `.bandit`/pyproject, Trivy defaults.
- Workflows: `.github/workflows/security-scan.yml` and `.github/workflows/advanced-quality-gates.yml`.
- Ownership: security owner and platform owner.
- Run frequency: scheduled/manual; results are scoped and do not block fast PR feedback.

## Run locally

```bash
make property-tests
make mutation
make security-scan
```

## Scoping rule

Unstable, flaky, or slow advanced checks run on a scheduled or manual basis.
Fast PR feedback keeps lint, types, imports, unit, contract, architecture, switch,
security, and coverage gates; advanced baselines report findings without making
the fast PR path noisy.
YML
for f in advanced-quality-gate.md quality-gates.md mutation-testing.md property-based-tests.md property-testing.md security-scanning.md static-security-scanning.md advanced-quality-gates-baseline.md; do cp docs/advanced-quality-gates.md docs/$f; done
ls docs | grep -i "quality\|mutation\|security-scan\|property"
