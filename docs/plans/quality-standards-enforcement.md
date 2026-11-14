# Standards Enforcement Status

Coverage is measured for `src/finsight` with branch coverage enabled.

## Global floor

- `pyproject.toml`: `fail_under = 50`
- `Makefile`: `COVERAGE_MIN ?= 50`
- Measured baseline: 50% (ratcheted in #139).

Migrations, `conftest.py`, and generated code are the only exclusions. Adapters
are not excluded to inflate the number.

## High-risk package ratchets

Domain and application aim for 85% coverage. Until they reach that baseline,
package-specific ratchets are enforced separately:

- `src/finsight/domain`: `DOMAIN_COVERAGE_MIN ?= 65` (`make coverage-domain`)
- `src/finsight/application`: `APPLICATION_COVERAGE_MIN ?= 29` (`make coverage-application`)

Raise these floors as the suite grows; do not lower them without a recorded reason.

Ratcheted in #140 (H25): domain 60 -> 65; application 10 -> 29, using targeted behavioral tests for Q&A orchestration, source viewer, metering, and tracing.

## Changed-line coverage

Changed lines in `src/finsight/domain` and `src/finsight/application` must be at
least 85% covered. Enforced via `diff-cover` (`make coverage-diff`,
`DIFF_COVERAGE_BASE ?= origin/main`). CI runs this on pull requests against
the PR base branch. Failures name uncovered changed lines.

## Placeholder guard (issue #74)

A CI-declared test suite fails when it contains no non-skipped tests. The
shared `tests/conftest.py` counts executed (non-skipped) tests and sets
exit status 1 when that count is zero. This prevents placeholder-only suites
from going green.

Placeholder-only suites are tracked explicitly until replaced:
- `tests/integration/` - placeholder-only (issue #74).
- `tests/golden/` - placeholder-only (issue #77).
- `tests/security/test_prompt_injection.py` - tracked placeholder
  (issues #74/#80).
- `tests/unit/switches/*` skip placeholders are guarded by the switch
  meta-test (`test_switch_coverage.py`).
