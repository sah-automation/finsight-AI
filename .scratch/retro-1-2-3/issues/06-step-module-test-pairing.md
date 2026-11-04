# 06: Module↔test-file architecture test for source viewer steps

**What to build:** An architecture test that enforces a 1:1 correspondence between public step modules in `src/finsight/application/source_viewer/steps/` and test files in `tests/unit/application/source_viewer/steps/`. This catches new step classes shipped without tests (which happened in #205, #206, #208, #209, #210).

**Blocked by:** #215 (ticket 01) — (needs clean pre-commit gate)

**Status:** ready-for-agent

- [ ] New test class `TestStepModuleHasTestFile` in `tests/architecture/test_invariants.py`
- [ ] Enumerates `src/finsight/application/source_viewer/steps/*.py` excluding `__init__.py`, `_*.py`, `README.md`
- [ ] For each module `foo.py`, asserts `tests/unit/application/source_viewer/steps/test_foo.py` exists
- [ ] Test runs on every PR via the architecture test suite
- [ ] Current tree passes (all existing step modules have test files)
- [ ] Adding a new step module without a test file fails the gate
