# 05: Remove BLE001/S110 from steps/*.py per-file ignores + fix violations

**What to build:** The `pyproject.toml` per-file-ignores block for `src/finsight/application/source_viewer/steps/*.py` includes `BLE001` (broad exception catch) and `S110` (try-except-pass). Remove these two entries, run `make lint`, and fix every newly exposed violation in the step files (narrow the catch, add logging with trace_id, or let propagate).

**Blocked by:** #215 (ticket 01) — (needs clean pre-commit gate)

**Status:** ready-for-agent

- [ ] `BLE001` and `S110` removed from `pyproject.toml` `[tool.ruff.lint.per-file-ignores]` for `steps/*.py`
- [ ] `make lint` passes on `src/finsight/application/source_viewer/steps/*.py`
- [ ] Every `except Exception:` in step files is either:
  - Narrowed to a specific exception type, or
  - Logs with trace_id (using the existing tracing port) before handling, or
  - Allows the exception to propagate
- [ ] No `try: ... except Exception: pass` or `return None` patterns remain
- [ ] All step tests still pass
