# Security Tests

Real security gates that replace the old `-k "security or ..."` name filter.

Run with:

```bash
make test-security
# or
uv run pytest tests/security -v -m security
```

**Coverage:**

- `test_company_isolation.py` — `RequestContext` requires `company_id`, and every
  public data-access method in `adapters/` and `domain/ports/` must accept it.
  The AST scanner is itself tested against a violating fixture.
- `test_cache_keys.py` — answer cache keys are deterministic, tenant-scoped, and
  sensitive to role, access scope, question, and document stamp.
- `test_permissions.py` — the `config/permissions.yaml` matrix is checked against
  the typed `Role`, `Category`, and `Action` enums and against the
  `users.role` check in the latest migration. Every role/action/category pair is
  asserted, retired role IDs are denied, and unknown roles have no default.
- `test_evidence.py` — empty, blank, or invalid citations cannot count as
  evidence.
- `test_pii_redaction.py` — sensitive structured-log fields are redacted, and
  business code cannot log question, answer, chunk, or prompt text directly.
- `test_secret_scanning_scope.py` — pre-commit, `make secrets`, and CI scan the
  same file set, including `tests/`.
- `test_prompt_injection.py` — intentionally pending until the input gate exists;
  the skip is visible rather than green-by-accident.

The suite runs in the CI `Security Tests` job, is required by `Summary`, and is
part of the coverage run so the security primitives cannot be removed without
lowering coverage.
