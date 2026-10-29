# Standards Enforcement Status

Coverage is measured for `src/finsight` with branch coverage enabled.

## Global floor

- `pyproject.toml`: `fail_under = 24`
- `Makefile`: `COVERAGE_MIN ?= 24`
- Measured baseline: 24.81% (current working tree).

Migrations, `conftest.py`, and generated code are the only exclusions. Adapters
are not excluded to inflate the number.

## High-risk package ratchets

Domain and application aim for 85% coverage. Until they reach that baseline,
package-specific ratchets are enforced separately:

- `src/finsight/domain`: `DOMAIN_COVERAGE_MIN ?= 60` (`make coverage-domain`)
- `src/finsight/application`: `APPLICATION_COVERAGE_MIN ?= 10` (`make coverage-application`)

Raise these floors as the suite grows; do not lower them without a recorded reason.

## Changed-line coverage

Changed lines in `src/finsight/domain` and `src/finsight/application` must be at
least 85% covered. Enforced via `diff-cover` (`make coverage-diff`,
`DIFF_COVERAGE_BASE ?= origin/main`). CI runs this on pull requests against
the PR base branch. Failures name uncovered changed lines.
