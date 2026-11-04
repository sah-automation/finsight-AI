# 02: Add `make ratchet` target

**What to build:** A `make ratchet` target that runs the standards checklist test with `UPDATE_STANDARDS_REPORT=1` so the tracked `standards_report.md` gets updated intentionally. This replaces the current workflow where the test rewrites the file on every run.

**Blocked by:** #215 (ticket 01) — (compare-only behavior must exist first)

**Status:** ready-for-agent

- [ ] `Makefile` has a `ratchet:` target
- [ ] Target runs `UPDATE_STANDARDS_REPORT=1 pytest tests/architecture/test_standards_checklist.py -v`
- [ ] Running `make ratchet` on a clean tree updates `standards_report.md` and exits 0
- [ ] Running `make ratchet` twice in a row produces no diff on the second run
