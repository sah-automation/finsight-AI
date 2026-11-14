# 08: Gate exception freshness check

**What to build:** A check that prevents `OVERSIZED_FILE_EXCEPTIONS` and `OVERSIZED_FUNCTION_EXCEPTIONS` entries from being added or widened in the same commit that creates/modifies the file they excuse. This stops the pattern where an oversized file gets an exception added in the same PR (as happened with `_request_to_context.py` in #210 and `_step_helpers.py` in #211).

**Blocked by:** None (can start immediately, but logically after WS1)

**Status:** ready-for-agent

- [ ] New test in `tests/architecture/test_invariants.py` (or a new file) that runs when `CHECK_EXCEPTION_FRESHNESS=1` (set in CI)
- [ ] For each exception entry, checks `git log --oneline -1 -- <excepted-file>` and fails if:
  - The most recent commit touching the file also touches `test_invariants.py` (the exception list), OR
  - The exception's `removal_condition` references the current ticket/PR number
- [ ] Simpler alternative (if git history check is flaky): document the rule in `CODING_STANDARDS.md` §3 and rely on code-review skill to enforce "exception edits must be in a separate commit"
- [ ] Current exception entries all pass (they were added in prior commits)
- [ ] Adding a new exception for a newly created file in the same commit fails
