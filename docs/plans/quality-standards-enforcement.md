# Standards Enforcement Roadmap

Status of the automated enforcement for `CODING_STANDARDS.md`.

## Implemented now

| Gate | Command | Enforces |
| --- | --- | --- |
| Style and lint | `make lint` (`ruff check`, `ruff format --check`) | formatting, imports, security rules, annotations |
| Types | `make typecheck` (`mypy --strict`) | type correctness in `src/` |
| Import architecture | `make imports` (`lint-imports`) | layer direction, vendor-import bans |
| Dead code | `make vulture` | unused code in `src/` |
| Secrets | `make secrets` (`detect-secrets`) | no committed credentials |
| Architecture invariants | `make arch-test` (`pytest tests/architecture`) | env reads, `company_id`, `Decimal` money, hidden construction, naming, READMEs |
| Switch paths | `make test-switches` | every `SwitchesConfig` field has ON and OFF tests |
| Suite markers | `tests/conftest.py` | `-m unit`, `-m integration`, etc. always select the right tests |

`make check` runs all of the above. `make ci` adds coverage. CI mirrors the same
commands in `.github/workflows/ci.yml`.

Deliberately **not** automated: one job per class, SOLID intent, "small boring
code", and naming quality. These stay in review and in the section 17
checklist.

## Remaining work

### 1. Enforce coverage with a ratchet

Current state: `pytest-cov` is configured, `fail_under = 0`, and no CI gate.

Plan:
1. Add `diff-cover` to dev dependencies.
2. In CI, run the unit and contract suites with `--cov-report=xml`.
3. Fail a PR when changed lines in `src/finsight/domain` or
   `src/finsight/application` are below 85% coverage.
4. Once `domain` and `application` have real code, add an absolute
   `fail_under = 85` for those packages only, not for adapters or entrypoints.
5. Record the current percentage in this document each time the absolute gate
   moves.

Definition of done: a PR that adds an untested branch in `domain` fails CI, and
the failure message names the uncovered lines.

### 2. Grow the architecture invariant suite

Current tests skip or are heuristic where code does not exist yet. Revisit each
when the target module lands:

- `TestMoneyUsesDecimal` currently skips because `domain/value_objects` has no
  `Money` yet. Remove the skip when `Money` exists.
- `TestFileClassNaming` has a fixed allow-list (`models.py`, `errors.py`,
  `types.py`, `loader.py`). Split those modules into one-class files, then
  delete the allow-list.
- Size limits currently print warnings. Turn them into failures once the
  baseline is clean.
- Add invariants not yet covered:
  - every `domain/ports` method is an abstract method;
  - every adapter class implements at least one port;
  - no `except Exception: pass` outside approved boundaries;
  - no `float` in `domain` or `application` annotations (not just value
    objects);
  - every `config/schema.yaml` switch has a typed field in `SwitchesConfig`.

Definition of done: no invariant is a no-op and each failure points at
`file:line`.

### 3. Make switch tests real as features land

Current state: ten test files exist with `pytest.skip`. The meta-test fails if a
switch is added without a file or without `_on`/`_off` tests.

Plan, for each feature PR:
1. Replace the two skips with a fake-driven test. Both branches must be
   exercised: ON uses the feature, OFF uses the documented fallback.
2. Assert the observable effect, not just that a collaborator was called.
3. For model swaps, assert the configured model ID is the one requested.

Definition of done: no skip remains in `tests/unit/switches` once the feature
exists.

### 4. Contract tests

Current state: placeholder only.

Plan:
1. For each port in `domain/ports`, add one contract test class parameterised
   over every adapter implementation.
2. Start with the ports that have the highest blast radius: LLM gateway,
   vector store, cache, repositories, queue.
3. Run contract tests against fakes in unit CI and against LocalStack/Postgres
   in the integration job.

Definition of done: adding a new adapter without passing the shared contract
test fails CI.

### 5. Golden set harness

Current state: placeholder only.

Plan:
1. Define the golden question file format (question, expected facts, required
   citations, tolerance).
2. Run the same set twice: `pilot` config and `standard` config.
3. Score on citation correctness and answer overlap, not exact string match.
4. Store a baseline score and fail when a change drops it by more than the
   agreed threshold.
5. Keep golden runs out of PR feedback time; run on a label or nightly.

Definition of done: a model or prompt change that degrades answers is blocked
before release.

### 6. Pull request checklist automation

Current state: section 17 is manual.

Plan:
1. Add `.github/pull_request_template.md` containing the section 17 checklist.
2. Add a CI check that fails when the checklist is not filled in (simple text
   match on the PR body), or use a `checklist` action.
3. Link the checklist items to the gates that enforce them, so reviewers know
   which items are machine-checked.

Definition of done: a PR cannot merge with an untouched checklist.

### 7. Secret scanning and dependency hygiene

- Tune `.secrets.baseline` after the first real adapters and config files land;
  never blanket-exclude `src/`.
- Add `pip-audit` (or `uv audit`) to CI for known-vulnerable dependencies.
- Add a scheduled job that runs `make check` against upgraded dependencies to
  catch drift before a release branch.
- Keep `uv.lock` committed. CI uses `--frozen`; an uncommitted lockfile breaks
  reproducible installs.

### 8. End-to-end gate verification

Before the first feature PR:
1. Push a throwaway commit that violates each rule (vendor import in
   `application`, missing `company_id`, `float` money, switch without a test)
   and confirm the matching gate fails.
2. Delete the throwaway branch.
3. Record the results in this document.

Definition of done: every implemented gate has been observed failing for the
reason it claims to catch.

## Order of work

1. End-to-end gate verification (cheap, proves the gate is real).
2. PR template and checklist automation.
3. Coverage ratchet.
4. Architecture invariant upgrades as modules land.
5. Switch tests as each feature lands.
6. Contract tests, then golden harness.
7. Dependency audit and scheduled upgrade job.
