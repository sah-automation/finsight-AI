# 01: Make test_standards_checklist.py compare-only

**What to build:** The architecture test `test_standards_checklist.py` currently rewrites the tracked file `tests/architecture/standards_report.md` on every run. This dirties the tree during the pre-commit `architecture-tests` hook, causing a stash-restore conflict that forces agents to use `git commit --no-verify`. Change the test to be compare-only: generate the report in memory, diff against the checked-in file, and fail with a clear message (`standards_report.md is stale; run \`make ratchet\` to update`) unless `UPDATE_STANDARDS_REPORT=1` is set.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] Test generates report to temporary path / in-memory string by default
- [ ] When `UPDATE_STANDARDS_REPORT=1` is set, writes the tracked file (for `make ratchet`)
- [ ] When env var is not set and report differs, `pytest.fail()` with "run `make ratchet`" message
- [ ] When env var is not set and report matches, test passes silently
- [ ] Existing `make ratchet` (to be added in ticket 02) works with this change
