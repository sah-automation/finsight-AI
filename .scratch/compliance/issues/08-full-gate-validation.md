# 08: Full gate validation and cleanup

**What to build:** Run all gates and fix any remaining issues. Ensure make check and make ci pass. Update tracking docs.

**Blocked by:** 07: Address file/function size limits if needed

**Status:** ready-for-agent

## Acceptance criteria
- [ ] Run `make lint` - must pass
- [ ] Run `make typecheck` - must pass
- [ ] Run `make imports` - must pass
- [ ] Run `make arch-test` - must pass
- [ ] Run `make test` - must pass
- [ ] Run `make test-security` - must pass
- [ ] Run `make check` - must pass
- [ ] Run `make ci` - must pass
- [ ] Update fix-tracker with final status
- [ ] Commit final state
