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
- [x] Phase 2 — Unsafe ruff fixes applied selectively (#58). Applied clearly behavior-preserving subset: `B007`, `F841`, `PERF102`, `RET504`, `SIM105` (most), `SIM108`, `TC001`, `TC003` via `--unsafe-fixes`; plus one manual `B007` rename and import sort safe fixes. Remaining unsafe (`SIM105` x1, `B007` x1, etc.) deferred. Lint 365 -> 296.
- [ ] Phase 3 — Manual fixes: type ignores (PGH003), TYPE_CHECKING imports (TC003/TC001), exception chaining (B904) (#59).
- [ ] Phase 4 — Manual fixes for remaining lint errors (S608, BLE001, SIM105, etc.) (#60).
- [x] Phase 5 — Structural compliance verify (#61): one class per file, names, no utils/helpers, every package README. Verified: `make arch-test` (45 passed), no multi-class files beyond allowed exceptions, no utils/helpers, all `src/finsight` packages have README.
- [ ] Phase 6 — File/function size limits if needed (#62).
- [ ] Phase 7 — Manual fixes remaining (this issue sequence consolidated).
- [ ] Phase 8 — Full gate validation and cleanup (#63): `make check` / `make ci` green, pre-commit green.

## Rule progress (target count → 0)

| Rule | Baseline | Fixed | Remaining |
|------|---------:|------:|----------:|
| ANN401 | 152 | 0 | 152 |
| BLE001 | 31 | 7 | 24 |
| PGH003 | 30 | 0 | 30 |
| TC001 | 28 | 28 | 0 |
| S608 | 22 | 0 | 22 |
| S110 | 19 | 7 | 12 |
| E501 | 16 | 0 | 16 |
| SIM105 | 11 | 10 | 1 |
| PLR0912 | 9 | 1 | 8 |
| TRY300 | 7 | 0 | 7 |
| F841 | 5 | 5 | 0 |
| TC003 | 5 | 5 | 0 |
| PLC0415 | 4 | 0 | 4 |
| PLR0915 | 4 | 0 | 4 |
| B023 | 4 | 0 | 4 |
| F401 | 3 | 0 | 3 |
| PLR0913 | 3 | 0 | 3 |
| SIM108 | 2 | 2 | 0 |
| B007 | 2 | 1 | 1 |
| S112 | 1 | 0 | 1 |
| PERF102 | 1 | 1 | 0 |
| TRY203 | 1 | 0 | 1 |
| PLW0127 | 1 | 0 | 1 |
| B025 | 1 | 0 | 1 |
| RUF060 | 1 | 0 | 1 |
| E402 | 1 | 0 | 1 |
| RET504 | 1 | 1 | 0 |
| **TOTAL** | **365** | **69** | **296** |

## Gate status (updated per phase)

| Gate | Baseline | Latest |
|------|----------|--------|
| `make lint` | FAIL 365 | FAIL 296 |
| `make typecheck` | PASS | PASS |
| `make imports` | PASS | PASS |
| `make arch-test` | PASS | PASS |
| `make test` | PASS | PASS |
| `make test-security` | PASS | PASS |
| `make check` / `make ci` | FAIL (lint) | FAIL (lint) |

## Commit log (audit-related)

- Phase 0 (#56): audit artifacts (this commit).
- Phase 1 (#57): safe ruff auto-fixes (no-op; 0 safe fixes); audit diff summary.
- Phase 2 (#58): selective unsafe ruff fixes (53 unsafe available, applied subset); lint 365 -> 296.

## Notes
- Only implementer of Phase 0 scoped work; subsequent phases tracked here.
- No code changes in Phase 0; audits only.
