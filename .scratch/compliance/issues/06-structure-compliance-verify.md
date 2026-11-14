# 06: Verify structure compliance

**What to build:** Verify all structural rules hold - one class per file, filename matches class name, no utils/helpers, every package has README. Fix if any violations found.

**Blocked by:** 05: Manual fixes for remaining lint errors

**Status:** ready-for-agent

## Acceptance criteria
- [ ] Run `make arch-test` - must pass
- [ ] Check for files with multiple public classes (beyond allowed exceptions)
- [ ] Check for utils.py/helpers.py
- [ ] Verify all packages have README.md
- [ ] Fix any violations found
- [ ] Commit if changes made
