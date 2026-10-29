# 03: Apply safe unsafe-fixes selectively

**What to build:** Evaluate unsafe ruff fixes (`--fix --unsafe-fixes`) category by category. Apply only those that are clearly safe and behavior-preserving (e.g. some TC003 moves may be fine; be very careful). Update tracker.

**Blocked by:** 02: Apply safe ruff auto-fixes

**Status:** ready-for-agent

## Acceptance criteria
- [ ] Try unsafe fixes on a small test first or apply per-rule
- [ ] For each category applied, run `make lint` and tests to verify no breakage
- [ ] Only apply fixes that don't change behavior
- [ ] Update lint-categories and fix-tracker with progress
- [ ] Commit in logical chunks
