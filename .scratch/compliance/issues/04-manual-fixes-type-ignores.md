# 04: Manual fixes for type ignores and imports

**What to build:** Fix PGH003 (add specific rule codes to type ignores), TC003 where not auto-fixed (move stdlib imports to TYPE_CHECKING), and related import issues. Focus on src/ first.

**Blocked by:** 03: Apply safe unsafe-fixes selectively

**Status:** ready-for-agent

## Acceptance criteria
- [ ] Fix all PGH003 violations - replace bare `# type: ignore` with specific codes
- [ ] Fix remaining TC003 violations appropriately
- [ ] Check `src/finsight/domain/ports/virus_scanner.py` and `src/finsight/domain/value_objects/virus_scan_result.py` specifically
- [ ] Run `make lint` frequently
- [ ] Ensure mypy still passes
- [ ] Commit changes
