# 05: Manual fixes for remaining lint errors

**What to build:** Fix all remaining ruff errors in src/ (and tests if necessary). Handle B904 (exception chaining), style issues, complexity if any. Follow existing patterns, no broad ignores.

**Blocked by:** 04: Manual fixes for type ignores and imports

**Status:** ready-for-agent

## Acceptance criteria
- [ ] Categorize remaining errors from tracker
- [ ] Fix systematically by file/rule
- [ ] For B904 add `from e` / `from err` appropriately
- [ ] Follow project style
- [ ] Run `make lint` after each batch
- [ ] Get `make lint` to pass with zero errors
- [ ] Commit
