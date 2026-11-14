# 09: `make sizes` target + helper script

**What to build:** A single `make sizes` command that reports file and function line counts, replacing the 14× `wc -l` / `sed -n` scripts agents currently run. Output should show:
- Files over 300 lines
- Public functions over 30 lines
- Private functions over 60 lines

**Blocked by:** None (can start immediately, but logically after WS1)

**Status:** ready-for-agent

- [ ] `Makefile` has a `sizes:` target
- [ ] Target runs in <3s
- [ ] Output format matches the example in the plan (three sections with clear headers)
- [ ] Helper script `tests/support/size_report.py` (or reuse `ast_inspection.py`) provides the function-level analysis
- [ ] Public functions use the existing 30-line threshold
- [ ] Private functions use the 60-line threshold from ticket 07
- [ ] Running `make sizes` on current tree produces readable output
