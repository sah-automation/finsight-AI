# 07: Address file/function size limits if needed

**What to build:** Check for files >300 lines and functions >30 lines. If found and they cause issues or need cleanup, refactor by extracting while maintaining SRP, layering, one-class-per-file where reasonable. Keep behavior identical.

**Blocked by:** 06: Verify structure compliance

**Status:** ready-for-agent

## Acceptance criteria
- [ ] Check arch test size warnings
- [ ] Identify oversized files/functions
- [ ] Refactor if necessary, maintaining all rules
- [ ] Run tests after each refactor
- [ ] Ensure gates still pass
- [ ] Commit
