# 02: Apply safe ruff auto-fixes

**What to build:** Apply all safe `ruff check --fix` changes to src and tests. Review diff, ensure behavior preserved. Reduce error count.

**Blocked by:** 01: Baseline audit and tracking

**Status:** ready-for-agent

## Acceptance criteria
- [ ] Run `uv run ruff check --fix src tests` (safe fixes only)
- [ ] Review changes for any suspicious modifications
- [ ] Run `make lint` and record new error count in fix-tracker
- [ ] Save diff summary to audit folder
- [ ] Commit changes
