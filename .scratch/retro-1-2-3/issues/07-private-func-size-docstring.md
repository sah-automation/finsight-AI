# 07: Private function size ratchet + public `run` docstring check

**What to build:** Two new architecture checks in `tests/architecture/test_invariants.py`:
1. Private function size limit: extend `TestSizeLimits` (or add a new class) to check `_`-prefixed functions with a separate ratchet baseline (e.g., `MAX_PRIVATE_FUNCTION_LINES = 60` initially).
2. Public `run` docstring check: AST-based check that every public `run` method in step classes has a docstring (`ast.get_docstring(node)` is not None).

**Blocked by:** #215 (ticket 01) — (needs clean pre-commit gate)

**Status:** ready-for-agent

- [ ] `MAX_PRIVATE_FUNCTION_LINES` constant added (initial value 60, ratchet down over time)
- [ ] Private function size check runs and passes on current tree (or failures are documented with exceptions)
- [ ] Public `run` docstring check runs and flags any step class missing a docstring on `run`
- [ ] Both checks integrated into the architecture test suite
- [ ] Ratchet mechanism: failures can be added to an exception dict with `reason`, `owner`, `removal_condition` (mirroring `OVERSIZED_FILE_EXCEPTIONS`)
