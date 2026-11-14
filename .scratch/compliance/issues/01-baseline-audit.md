# 01: Baseline audit and tracking

**What to build:** A complete, categorized audit of all lint violations so fixes can be tracked systematically. Must capture exact errors for `make lint`, `make test`, `make test-security`, `make check`/`make ci` state.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

## Acceptance criteria
- [ ] Run `make lint` and save full output to `docs/plans/compliance/audit/lint-baseline.txt`
- [ ] Parse and categorize errors by rule code (PGH003, TC003, B904, etc.) with counts
- [ ] Create `docs/plans/compliance/audit/lint-categories.md` with breakdown
- [ ] Run `make test 2>&1 | tail -60` and save to `docs/plans/compliance/audit/test-baseline.txt`
- [ ] Run `make test-security 2>&1 | tail -40` and save to `docs/plans/compliance/audit/security-baseline.txt`
- [ ] Create `docs/plans/compliance/audit/fix-tracker.md` to track progress
- [ ] Commit audit artifacts
