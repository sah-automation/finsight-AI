# Fix Tracker — Codebase Compliance (issue #55 / slices #56–#63)

Tracks progress toward closing all lint/type/import/arch/test/security gates. See spec:
`docs/plans/compliance/codebase-compliance-hard-gates-spec.md`.

## Baseline (captured by #56)

- Lint errors: **365** (all `src/finsight/`). | Details: `lint-categories.md`, `lint-baseline.txt`
- Typecheck: clean | Imports: clean | Arch tests: clean
- Tests (`make test`): green | Security (`make test-security`): green

## Phases

- [x] Phase 0 — Baseline audit and tracking (#56). Artifacts in `docs/plans/compliance/audit/`.
- [x] Phase 1 — Safe ruff auto-fixes (#57). Ran `uv run ruff check --fix src tests` (safe only): 0 safe fixes available, 365 errors remain; 53 unsafe fixes deferred to Phase 2. Diff summary: `audit/diff-phase1-safe.txt`.
- [ ] Phase 2 — Unsafe ruff fixes applied selectively (#58).
- [ ] Phase 3 — Manual fixes: type ignores (PGH003), TYPE_CHECKING imports (TC003/TC001), exception chaining (B904) (#59).
- [ ] Phase 4 — Manual fixes for remaining lint errors (S608, BLE001, SIM105, etc.) (#60).
- [ ] Phase 5 — Structural compliance verify (#61): one class per file, names, no utils/helpers, every package README.
- [ ] Phase 6 — File/function size limits if needed (#62).
- [ ] Phase 7 — Manual fixes remaining (this issue sequence consolidated).
- [ ] Phase 8 — Full gate validation and cleanup (#63): `make check` / `make ci` green, pre-commit green.

## Rule progress (target count → 0)

| Rule | Baseline | Fixed | Remaining |
|------|---------:|------:|----------:|
| ANN401 | 152 | 0 | 152 |
| BLE001 | 31 | 0 | 31 |
| PGH003 | 30 | 0 | 30 |
| TC001 | 28 | 0 | 28 |
| S608 | 22 | 0 | 22 |
| S110 | 19 | 0 | 19 |
| E501 | 16 | 0 | 16 |
| SIM105 | 11 | 0 | 11 |
| PLR0912 | 9 | 0 | 9 |
| TRY300 | 7 | 0 | 7 |
| F841 | 5 | 0 | 5 |
| TC003 | 5 | 0 | 5 |
| PLC0415 | 4 | 0 | 4 |
| PLR0915 | 4 | 0 | 4 |
| B023 | 4 | 0 | 4 |
| F401 | 3 | 0 | 3 |
| PLR0913 | 3 | 0 | 3 |
| SIM108 | 2 | 0 | 2 |
| B007 | 2 | 0 | 2 |
| S112 | 1 | 0 | 1 |
| PERF102 | 1 | 0 | 1 |
| TRY203 | 1 | 0 | 1 |
| PLW0127 | 1 | 0 | 1 |
| B025 | 1 | 0 | 1 |
| RUF060 | 1 | 0 | 1 |
| E402 | 1 | 0 | 1 |
| RET504 | 1 | 0 | 1 |
| **TOTAL** | **365** | **0** | **365** |

## Gate status (updated per phase)

| Gate | Baseline | Latest |
|------|----------|--------|
| `make lint` | FAIL 365 | FAIL 365 |
| `make typecheck` | PASS | PASS |
| `make imports` | PASS | PASS |
| `make arch-test` | PASS | PASS |
| `make test` | PASS | PASS |
| `make test-security` | PASS | PASS |
| `make check` / `make ci` | FAIL (lint) | FAIL (lint) |

## Commit log (audit-related)

- Phase 0 (#56): audit artifacts (this commit).
- Phase 1 (#57): safe ruff auto-fixes (no-op; 0 safe fixes); audit diff summary.

## Notes
- Only implementer of Phase 0 scoped work; subsequent phases tracked here.
- No code changes in Phase 0; audits only.
