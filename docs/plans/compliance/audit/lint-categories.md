# Lint Baseline — Categorization

Source: `docs/plans/compliance/audit/lint-baseline.txt` (full `make lint` output captured 2026-10-29).
Result: **365 errors**, all in `src/finsight/` (no test-file errors). mypy --strict, import-linter, architecture tests, and vulture are green at baseline.

## By rule code (365 total)

| Rule | Count | Category / typical fix approach |
|------|------:|------------------------------|
| ANN401 | 152 | Dynamically typed `Any` (disallowed). Re-type or add targeted per-file ignores where port surfaces stay dynamic; manual. |
| BLE001 | 31 | Blind `Exception` catch. Narrow exception types; re-raise; manual. |
| PGH003 | 30 | `# type: ignore` without explicit code. Add specific error codes. |
| TC001/TC003 | 33 | Imports movable into `TYPE_CHECKING` (28 + 5). TC003 = standard lib, TC001 = app imports. |
| S608 | 22 | Possible SQL injection via string query. Verify parameter binding / sanitisation; manual. |
| S110 | 19 | `try/except/pass`. Consider logging; convert to `contextlib.suppress` or log. |
| E501 | 16 | Line too long (>100). Format manual. |
| SIM105 | 11 | Use `contextlib.suppress`. |
| PLR0912 | 9 | Too many branches (>12). Refactor. |
| TRY300 | 7 | Move to `else` block. |
| F841 | 5 | Unused local variable. |
| PLC0415 | 4 | Top-level import. |
| PLR0915 | 4 | Too many statements (>50). |
| B023 | 4 | Loop-variable binding in nested func. |
| F401 | 3 | Unused import. |
| PLR0913 | 3 | Too many arguments (>5). |
| SIM108 | 2 | Ternary suggestion. |
| B007 | 2 | Unused loop variable. |
| S112 | 1 | `try/except/continue`. |
| PERF102 | 1 | Use dict values. |
| TRY203 | 1 | Exception handler immediately re-raised — remove. |
| PLW0127 | 1 | Self-assignment. |
| B025 | 1 | Duplicate except clause. |
| RUF060 | 1 | Unnecessary membership test on empty collection. |
| E402 | 1 | Module-level import not at top. |
| RET504 | 1 | Unnecessary assignment before return. |

(ANN401 count is 152 — single largest bucket. PGH003 count is 30.)

Safe auto-fixes available from ruff: 53 unsafe fixes; see `ruff check --unsafe-fixes` review.

## By layer

| Layer | Errors |
|-------|-------:|
| adapters | 234 |
| domain | 114 |
| application | 14 |
| core | 3 |

Adapter sub-buckets: repositories 95, cache 77, partitions 62.

## Top files

| Errors | File |
|-------:|------|
| 77 | src/finsight/adapters/cache/job_progress.py |
| 62 | src/finsight/adapters/partitions/partition_manager.py |
| 48 | src/finsight/domain/ports/job_progress_port.py |
| 35 | src/finsight/adapters/repositories/job_repository.py |
| 33 | src/finsight/adapters/repositories/base_repository.py |
| 12 | src/finsight/domain/ports/job_repository.py |
| 11 | src/finsight/adapters/repositories/company_repository.py |
| 10 | src/finsight/domain/ports/answer_cache.py |
| 9  | src/finsight/adapters/repositories/user_repository.py |
| 7  | src/finsight/... (partition_metadata_repository, document_reader, object_storage) |

## Gate status at baseline

- `make lint`: **FAIL** (365 errors, exit 2) — see `lint-baseline.txt`
- `make typecheck`: PASS (0 issues, 298 files)
- `make imports`: PASS (10 kept, 0 broken)
- `make arch-test`: PASS (45 passed)
- `make vulture`: PASS
- `make secrets`: PASS
- `make test`: PASS (all suites; 9 passed + 24 skipped switches, 45 arch)
- `make test-security`: PASS (338 passed, 1 skipped)
- `make check`: FAILS at lint gate (stops there)
- `make ci`: FAILS at lint gate (stops there)

## Notes / caveats

- Per-file ignores in `pyproject.toml` already exempt many rules in specific modules (update/delete/reprocess/ingest use cases, onboarding, storage, workers, composition, upload endpoint). Do NOT broaden them; respect existing targeted ignores (CODING_STANDARDS §9, §17).
- The errors above are what remains after current ignores.
- Pattern for TC001/TC003: move imports into `TYPE_CHECKING` blocks (safe if runtime-resolvable).
- No rule disabling without PR justification.

## Phase 2 progress (#58)

Applied selective unsafe ruff fixes (53 available; applied 49 via tool + 1 manual):
B007 -1, F841 -5, PERF102 -1, RET504 -1, SIM105 -10, SIM108 -2, TC001 -28, TC003 -5, plus contextlib.suppress conversions reducing BLE001 -7, S110 -7, S608 unchanged, PLR0912 -1.

Remaining lint error count: **296** (was 365).
