# Development Infrastructure Implementation Plan

Status: P0 implemented (DI-01 to DI-06 and DI-25 are closed; DI-17 is also implemented. See sections 13 and 14 for execution logs)
Date: 2026-10-26
Source: static review of the repository, CI workflow, local service stack, OpenCode configuration, and the GitHub remote, followed by an execution pass on a machine with Docker
Scope: development, CI, local environment, repository governance, and deployment scaffolding
Out of scope: product/business features, model selection, prompt design, and application code beyond what is needed to make the infrastructure gates work

This plan records every development-infrastructure gap found during the review. It is ordered so that each step unblocks the next. Items are not estimates; each one has concrete files and acceptance criteria.

---

## 1. How to use this plan

- Work top to bottom. P0 items must be closed before trusting any CI result.
- One pull request per workstream unless two items are inseparable (for example, local environment reconciliation and `.env.example`).
- Every item has **Evidence**, **Change**, **Acceptance criteria**, and **Verify**.
- Update this file when an item is completed or deliberately deferred. Add the PR number next to the item.
- Do not weaken a gate to make it pass. If a gate is wrong, change the gate and record why.

### Priority definitions

| Priority | Meaning |
| --- | --- |
| P0 | Blocks a working development or CI loop, or creates a security/legal exposure. Fix first. |
| P1 | Missing infrastructure or gate that the project already promises. Fix before feature work scales. |
| P2 | Gate exists but is weaker than it appears, or tool versions drift between local, pre-commit, and CI. |
| P3 | Production/deployment work that can start after P0/P1 are stable. |
| Docs | Documentation and repository hygiene that misleads new contributors or agents. |

### Files this plan adds or changes

Documentation and configuration only at first. No application-layer code is required except where explicitly noted (the `test` config profile in DI-05 and the architecture-test fixes in DI-15).

| Area | Files |
| --- | --- |
| This plan | `docs/plans/dev-infra-implementation-plan.md` |
| Access control | `opencode.json` |
| CI | `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`, `.github/dependabot.yml`, `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/`, `.github/CODEOWNERS` |
| Local environment | `config/test.yaml`, `config/dev.yaml`, `docker-compose.test.yml`, `infra/localstack/init.sh`, `.env.example` |
| Tooling | `.pre-commit-config.yaml`, `Makefile`, `.python-version`, `pyproject.toml`, `tests/architecture/test_invariants.py`, `.secrets.baseline` |
| Migrations | `alembic.ini`, `migrations/` |
| Packaging and deploy | `Dockerfile`, `.dockerignore`, `infra/`, `scripts/` |
| Docs and repo hygiene | `README.md`, `docs/README.md`, `CONTRIBUTING.md`, `LICENSE`, `.editorconfig`, `src/finsight/README.md` |

---

## 2. Workstream summary

| ID | Priority | Workstream | Blocks |
| --- | --- | --- | --- |
| DI-01 | P0 | Push `main` and protect it | Trusting CI, all later merges |
| DI-02 | P0 | Remove invalid `cache: uv` from all CI jobs | Every CI job |
| DI-03 | P0 | Resolve public repository vs proprietary license | Legal/security exposure |
| DI-04 | P0 | Install hooks and fix the `commit-msg` no-op | Local quality gate |
| DI-05 | P0 | Reconcile dev compose/LocalStack/CI configuration | Integration tests |
| DI-06 | P0 | Add `.env.example` | Onboarding, local runs |
| DI-07 | P1 | Add Alembic migrations | Schema evolution |
| DI-08 | P1 | Run pre-commit in CI | YAML/shell/large-file gates |
| DI-09 | P1 | Enforce coverage | Quality ratchet |
| DI-10 | P1 | Add dependency and security scanning | Supply chain |
| DI-11 | P1 | Add PR/issue templates, CODEOWNERS, Dependabot | Review quality |
| DI-12 | P1 | Complete the Makefile and remove duplicate work | Developer ergonomics |
| DI-13 | P1 | Commit `.python-version` | Reproducible Python |
| DI-14 | P2 | Complete import-linter contracts | Architecture enforcement |
| DI-15 | P2 | Fix dead architecture-test checks | Architecture enforcement |
| DI-16 | P2 | Replace the `security-tests` name filter | Security confidence |
| DI-17 | P2 | Run mypy through the locked `uv` environment | Tool version drift |
| DI-18 | P2 | Align detect-secrets scope | Secret scanning |
| DI-19 | P2 | Align the CI `uv` version with the lockfile | Reproducibility |
| DI-20 | P3 | Add infrastructure as code | Deployability |
| DI-21 | P3 | Add container/Lambda packaging | Deployability |
| DI-22 | P3 | Add deploy/release/rollback workflow | Operations |
| DI-23 | Docs | Fix README and documentation gaps | Onboarding |
| DI-24 | Docs | Resolve unused config files and missing root docs | Maintainability |
| DI-25 | P0 | Protect requirement and architecture documents | Accidental edits |

---

## 3. P0 — blocks a working development or CI loop

### DI-01 — Push `main` and protect it

**Evidence**

- `git status -sb` shows `main` with no upstream.
- `git ls-remote --heads origin` returns nothing.
- GitHub reports repository size `0`, no workflows, and a 404 for `branches/main/protection`.
- The single local commit is `d167aef chore: initial project skeleton and standards enforcement gate`.
- CI has therefore never executed, and no required check can be configured yet.

**Change**

1. Push the initial commit: `git push -u origin main`.
2. Create a repository ruleset (or branch protection rule) on `main`:
   - Require a pull request before merging.
   - Require the `Summary` check from `.github/workflows/ci.yml` and the new pre-commit job from DI-08.
   - Require branches to be up to date before merging.
   - Block force pushes and branch deletion.
   - Require conversation resolution.
3. Add `develop` only if the team actually uses it. The workflow already listens for `develop`; do not create a dead branch just to match the YAML.
4. Record the ruleset name and required checks in `CONTRIBUTING.md` (DI-23).

**Acceptance criteria**

- `origin/main` exists and points at the pushed commit.
- A direct push to `main` is rejected.
- A pull request shows the required checks and cannot merge while `Summary` is red.
- `gh api repos/sah-automation/finsight-AI/branches/main/protection` succeeds (or the equivalent ruleset API returns the rule).

**Verify**

```bash
git ls-remote --heads origin
gh api repos/sah-automation/finsight-AI/branches/main/protection
gh run list --limit 5
```

---

### DI-02 — Remove invalid `cache: uv` from all CI jobs

**Evidence**

- `.github/workflows/ci.yml` passes `cache: uv` to `actions/setup-python@v5` in all nine jobs: lines 32, 73, 99, 135, 161, 188, 243, 276, and 303.
- `actions/setup-python` supports only `pip`, `pipenv`, and `poetry` for the `cache` input. An unsupported value fails the step before dependency installation.
- `astral-sh/setup-uv@v4` already has `enable-cache: true` in every job, so the setup-python cache is redundant even if it were valid.

**Change**

- Remove every `cache: uv` line from `.github/workflows/ci.yml`.
- Leave `enable-cache: true` on `astral-sh/setup-uv`.
- Optional: replace the duplicated `python-version: ${{ env.PYTHON_VERSION }}` blocks with `python-version-file: .python-version` after DI-13.

**Acceptance criteria**

- No `cache: uv` remains in any workflow.
- A CI run reaches dependency installation in every job.
- The `lint-and-typecheck` job completes on a pull request.

**Verify**

```bash
grep -R "cache: uv" .github/workflows || echo "none"
gh run watch
```

---

### DI-03 — Resolve public repository vs proprietary license

**Evidence**

- `gh repo view sah-automation/finsight-AI` reports `"visibility": "PUBLIC"`.
- `README.md:191-193` says `Proprietary - All rights reserved.`
- `pyproject.toml:7` declares `license = {text = "Proprietary"}`.
- There is no `LICENSE` file at the repository root.

**Change**

Choose one and apply it consistently:

- **Option A (recommended for a commercial product):** make the repository private, keep `Proprietary`, and add a `LICENSE` file containing the proprietary notice and usage restrictions.
- **Option B:** keep the repository public and add an explicit `LICENSE` (for example, Apache-2.0 or MIT) and update `README.md` and `pyproject.toml` to match.
- **Option C:** keep it public but add a `LICENSE` that grants no rights (source-available). This is legally distinct from open source; make the wording explicit.

Do not leave a public repository with a "Proprietary" claim and no license file. That is the worst of both positions.

**Acceptance criteria**

- Repository visibility and license text agree.
- `LICENSE` exists and is referenced from `README.md`.
- `pyproject.toml` uses a license expression or text that matches the file.
- If the repo becomes private, GitHub Actions and branch protection still work for the team.

**Verify**

```bash
gh repo view sah-automation/finsight-AI --json visibility
head -20 LICENSE
grep -n "License" README.md pyproject.toml
```

---

### DI-04 — Install hooks and fix the `commit-msg` no-op

**Status: partly implemented.** The hook set now runs cleanly (see DI-17), but the hooks were not installed into `.git/hooks` and no `commit-msg` hook was added.

**Evidence**

- `.git/hooks` contains only `*.sample` files, so hooks are not installed in this clone.
- `Makefile:54-56` runs both `pre-commit install` and `pre-commit install --hook-type commit-msg`.
- `.pre-commit-config.yaml` defines no hook with `stages: [commit-msg]` (or the legacy `commit-msg` stage), so the installed `commit-msg` hook is a no-op.

**Change**

1. Run `make install-hooks` locally and document it in `CONTRIBUTING.md`.
2. Add a real commit-message check. Preferred: a local hook that enforces Conventional Commits (for example, `compilerla/conventional-pre-commit`) with `stages: [commit-msg]`.
3. Keep the hook list small; do not add a commit-msg linter that rejects the existing commit style without agreement.
4. Decide whether `make install-dev` should install hooks automatically or keep it explicit. Document the choice.

**Acceptance criteria**

- `.git/hooks/pre-commit` and `.git/hooks/commit-msg` are executable.
- A commit with a non-conforming message fails before the commit is created.
- A conforming message passes.
- `pre-commit run --all-files` succeeds on a clean tree.

**Verify**

```bash
make install-hooks
ls -l .git/hooks/pre-commit .git/hooks/commit-msg
pre-commit run --all-files
```

---

### DI-05 — Reconcile dev compose, LocalStack, and CI configuration

**Evidence**

The local stack has three disagreeing sources of truth:

| Resource | `config/dev.yaml` | `docker-compose.test.yml` / `infra/localstack/init.sh` | CI integration env |
| --- | --- | --- | --- |
| Database | `finsight_dev`, `postgres:postgres` | `test`, `test:test` | `test`, `test:test` |
| S3 buckets | `finsight-dev-documents`, `finsight-dev-reports`, `finsight-dev-backups` | `documents`, `reports`, `backups` | `test`, `test`, `test` |
| SQS queues | `finsight-dev-ingestion`, `finsight-dev-reprocessing`, `finsight-dev-reports`, `finsight-dev-dlq` | `ingestion`, `reprocessing`, `reports`, `dlq` | `http://localhost:4566/.../ingestion` etc. |
| DynamoDB tables | `finsight-dev-answer-cache`, `finsight-dev-role-cache`, `finsight-dev-metering` | `answer_cache`, `role_cache`, `metering` | `test` |
| AWS endpoint | not set | LocalStack on `:4566` | not set |
| AWS credentials | not set | `test` / `test` for LocalStack | not set |
| `ENVIRONMENT` | defaults to `development` in `src/finsight/core/config/loader.py` | not set | not set |

Consequences:

- CI's `VECTOR_DB_*`, `*_BUCKET`, and `*_QUEUE_URL` variables are overridden by literals in `config/dev.yaml`, because the loader defaults to `development` and `ENVIRONMENT` is never set in the integration job.
- LocalStack resources created by `infra/localstack/init.sh` do not match the names the adapters read from `dev.yaml`.
- `gh` test env sets `DOCUMENTS_BUCKET=test` but LocalStack creates `documents`, so the value is wrong even if it won.
- Using `staging` is not a fix: `config/staging.yaml:39` sets `ssl_mode: require`, which local Postgres does not support.
- `docker compose up -d; sleep 10` (`.github/workflows/ci.yml:195-196`) is a race. Use `--wait`.

**Change (recommended: add a real `test` profile)**

1. Add `Environment.TEST = 'test'` to `src/finsight/core/config/models.py`.
2. Add `config/test.yaml` with values that match the compose stack and LocalStack init script:
   - `app.environment: "test"`
   - vector store: `localhost:5432`, database `test`, user/password `test`, `ssl_mode: disable`
   - buckets: `documents`, `reports`, `backups`
   - queues: the LocalStack URLs created by `init.sh`
   - caches: `answer_cache`, `role_cache`
   - metering: `metering`
   - auth: LocalStack-safe dummy values
   - observability: local OTLP endpoint
3. Set `ENVIRONMENT: test` in the CI integration job and in the golden-test job where a non-production profile is intended.
4. Replace CI resource env vars with values consistent with `config/test.yaml`; do not duplicate literals in both places. Prefer env vars only for genuinely environment-specific overrides.
5. Add dummy AWS variables to the integration job:
   - `AWS_ACCESS_KEY_ID=test`
   - `AWS_SECRET_ACCESS_KEY=test`
   - `AWS_DEFAULT_REGION=us-east-1`
   - `AWS_ENDPOINT_URL=http://localhost:4566` (and any SDK-specific endpoint variable the adapters use)
6. Replace `docker compose up -d; sleep 10` with `docker compose up -d --wait`.
7. Optionally add a `test` target in the Makefile that runs the integration suite against the compose stack.
8. Update `tests/unit/core/config/test_loader.py` for the new environment if the enum change requires it.

**Alternative (smaller but less clean)**

Align `config/dev.yaml`, `infra/localstack/init.sh`, and `docker-compose.test.yml` on one naming scheme (`finsight-dev-*`) and remove the CI resource overrides. This avoids a new enum but couples developer defaults to CI. Prefer the `test` profile.

**Acceptance criteria**

- With `ENVIRONMENT=test`, the loader reads `config/test.yaml`, not `config/dev.yaml`.
- The integration job starts the stack with `--wait` and runs with no missing AWS endpoint or credential errors.
- A test that writes to `documents`/`ingestion` uses the same names LocalStack created.
- No CI env variable is silently shadowed by a YAML literal.
- `make test-integration` works on a machine with Docker installed.

**Verify**

```bash
ENVIRONMENT=test uv run python -c "from finsight.core.config import load_config; c=load_config(); print(c.app.environment, c.storage.documents_bucket)"
docker compose -f docker-compose.test.yml up -d --wait
ENVIRONMENT=test uv run pytest tests/integration -v -m integration
docker compose -f docker-compose.test.yml down -v
```

---

### DI-06 — Add `.env.example`

**Evidence**

- No `.env.example` exists.
- `.gitignore` ignores `.env`, `.env.local`, and `.env.*.local` (lines 103-105), so there is no committed template.
- Required local variables are spread across `config/dev.yaml`, `config/staging.yaml`, ``.github/workflows/ci.yml`, and adapter expectations.

**Change**

Add `.env.example` with grouped, commented entries:

- Runtime: `ENVIRONMENT=development`
- Vector database: `VECTOR_DB_HOST`, `VECTOR_DB_PORT`, `VECTOR_DB_NAME`, `VECTOR_DB_USER`, `VECTOR_DB_PASSWORD`
- AWS/LocalStack: `AWS_REGION`, `AWS_DEFAULT_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL`
- Storage: `DOCUMENTS_BUCKET`, `REPORTS_BUCKET`, `BACKUPS_BUCKET`
- Queues: `INGESTION_QUEUE_URL`, `REPROCESSING_QUEUE_URL`, `REPORTS_QUEUE_URL`, `DLQ_URL`
- Caches/metering: `ANSWER_CACHE_TABLE`, `ROLE_CACHE_TABLE`, `METERING_TABLE`
- Auth: `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`
- Observability: `OTLP_ENDPOINT`
- Model providers: placeholder names only, never real keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`)

Rules:

- Values must be safe dummy values, never real secrets.
- Every variable must have a one-line comment saying what it controls.
- Reference the file from `README.md` and `CONTRIBUTING.md`.

**Acceptance criteria**

- A new contributor can copy `.env.example` to `.env`, start the stack, and run the test suite without searching the codebase for variable names.
- `detect-secrets` does not flag the file.
- `.env.example` is not ignored by `.gitignore`.

**Verify**

```bash
git check-ignore .env.example || echo "not ignored"
uv run detect-secrets-hook --baseline .secrets.baseline .env.example
```

---

## 4. P1 — missing infrastructure and gates

### DI-07 — Add Alembic migrations

**Evidence**

- `alembic>=1.13.0,<2` is a dependency (`pyproject.toml:19`).
- `pyproject.toml:153-157` omits `*/migrations/*` from coverage, implying migrations were planned.
- There is no `alembic.ini` and no `migrations/` tree anywhere in the repository.
- `infra/postgres/init.sql` only creates the `vector` and `uuid-ossp` extensions.
- No schema migration exists for documents, chunks, metrics, answers, audit logs, or tenant tables.

**Change**

1. Add `alembic.ini` at the repository root.
2. Add `migrations/env.py`, `migrations/script.py.mako`, and `migrations/versions/`.
3. Wire `env.py` to the application's config/secret source; do not hardcode a database URL.
4. Add an initial migration that creates the core schema and `CREATE EXTENSION IF NOT EXISTS vector`.
5. Add `make migrate` and `make migration m="..."` targets (DI-12).
6. Add a CI check that `alembic upgrade head` succeeds against the compose Postgres, and optionally `alembic check` for model drift.
7. Document the migrate workflow in `CONTRIBUTING.md`.

**Acceptance criteria**

- `alembic upgrade head` creates the schema on an empty database.
- `alembic downgrade base` succeeds.
- `alembic upgrade head` is idempotent on an already-migrated database.
- CI fails if a model change has no migration (if `alembic check` is adopted).

**Verify**

```bash
docker compose -f docker-compose.test.yml up -d --wait postgres
ENVIRONMENT=test uv run alembic upgrade head
ENVIRONMENT=test uv run alembic downgrade base
ENVIRONMENT=test uv run alembic upgrade head
```

---

### DI-08 — Run pre-commit in CI

**Evidence**

- `.pre-commit-config.yaml` includes `yamllint`, `shellcheck`, `check-yaml`, `check-toml`, `check-added-large-files`, `end-of-file-fixer`, `trailing-whitespace`, `mixed-line-ending`, and `detect-private-key`.
- `.github/workflows/ci.yml` has no pre-commit job.
- Those checks therefore run only on machines where hooks are installed, and hooks are not installed by default (DI-04).

**Change**

1. Add a `pre-commit` job to `.github/workflows/ci.yml`:
   - Checkout.
   - Install `uv`.
   - Run `uv run pre-commit run --all-files --show-diff-on-failure`.
2. Add the job to the `summary` job's `needs` list and failure check.
3. Decide whether pre-commit replaces any duplicated CI steps. Keep `ruff`/`mypy` in CI even if pre-commit runs them, or make pre-commit the single source and remove duplicates deliberately.
4. Cache pre-commit environments if job time becomes a problem.

**Acceptance criteria**

- The job fails on a malformed YAML file, a shellcheck error, or a large file.
- The job passes on the current tree after required fixes.
- `Summary` fails when the pre-commit job fails.

**Verify**

```bash
uv run pre-commit run --all-files --show-diff-on-failure
gh run list --workflow ci.yml --limit 3
```

---

### DI-09 — Enforce coverage

**Evidence**

- `pyproject.toml:162` sets `fail_under = 0`.
- `.github/workflows/ci.yml` runs coverage but does not enforce a threshold.
- `docs/plans/quality-standards-enforcement.md` describes a ratchet that is still open.
- The latest `coverage.xml` reports line rate `0.5445` and branch rate `0.3966`.

**Change**

1. Set an initial floor that the current suite actually passes, for example `fail_under = 50`.
2. Add a coverage step to CI that fails below the floor:
   - `uv run pytest ... --cov=src/finsight --cov-report=term-missing --cov-report=xml --cov-fail-under=50`
3. Raise the floor in agreed increments (for example 50 → 60 → 70 → 80) as the suite grows. Record each bump in `docs/plans/quality-standards-enforcement.md`.
4. Exclude only genuinely untestable code (migrations, conftest, generated code). Do not exclude adapters to hit the number.
5. Upload `coverage.xml` as an artifact for inspection.

**Acceptance criteria**

- Lowering coverage below the floor fails CI.
- The floor is documented and ratcheted, not static at zero.
- Coverage is measured for `src/finsight`, with branch coverage on.

**Verify**

```bash
uv run pytest tests/unit tests/contract tests/architecture --cov=src/finsight --cov-fail-under=50
```

---

### DI-10 — Add dependency and security scanning

**Evidence**

- No Dependabot/Renovate config.
- No `pip-audit`, `uv audit`, CodeQL, or dependency-review workflow.
- No scheduled dependency update job.
- `uv.lock` is committed, which makes scanning deterministic and cheap.

**Change**

1. Add `.github/dependabot.yml` for:
   - `pip` / `uv` ecosystem on `/` (weekly).
   - `github-actions` on `/` (weekly).
2. Add a dependency-audit job or step: `uvx pip-audit --requirement <(uv export --format requirements-txt)` or the supported `pip-audit` invocation for the lockfile.
3. Add `actions/dependency-review-action` on `pull_request`.
4. Optional: enable CodeQL for Python (`.github/workflows/codeql.yml`).
5. Decide the policy for findings: fail on high/critical, open an issue for medium, allow documented exceptions in a checked-in file.

**Acceptance criteria**

- Dependabot opens grouped update PRs on schedule.
- A known vulnerable dependency fails the audit gate or is explicitly waived.
- PRs that introduce a vulnerable dependency are blocked or annotated.

**Verify**

```bash
gh pr list --label dependencies
gh run list --workflow codeql.yml
uvx pip-audit --version
```

---

### DI-11 — Add PR/issue templates, CODEOWNERS, and Dependabot config

**Evidence**

- No `.github/pull_request_template.md`.
- No `.github/ISSUE_TEMPLATE/`.
- No `.github/CODEOWNERS`.
- `docs/plans/quality-standards-enforcement.md` calls for a PR template with the section-17 checklist.
- GitHub Issues are enabled and the five triage labels already exist.

**Change**

1. Add `.github/pull_request_template.md` with:
   - Summary and linked issue.
   - Layer(s) touched.
   - The section-17 checklist from `CODING_STANDARDS.md`.
   - Tests added (unit, contract, switch paths).
   - Config switches changed.
   - Rollback note for risky changes.
2. Add issue templates: bug report, feature request, and infrastructure task. Include the triage labels where appropriate.
3. Add `.github/CODEOWNERS` for `src/finsight/core/`, `config/`, `infra/`, `.github/`, and `docs/plans/project_requirement/`.
4. Add `.github/dependabot.yml` (see DI-10).
5. Optional: add a `FUNDING` or `SECURITY.md` if the project publishes one. At minimum add `SECURITY.md` with a private disclosure path, especially if DI-03 keeps the repo public.

**Acceptance criteria**

- New PRs render the checklist automatically.
- Issue creation offers the templates.
- CODEOWNERS requests the right reviewers.
- `SECURITY.md` exists if the repo remains public.

**Verify**

```bash
ls .github .github/ISSUE_TEMPLATE
git check-ignore .github/CODEOWNERS || echo "tracked"
```

---

### DI-12 — Complete the Makefile and remove duplicate work

**Evidence**

- `Makefile:61` runs `check: lint typecheck imports vulture secrets arch-test test`.
- `Makefile:92` runs `test: test-unit test-contract test-architecture test-switches`.
- `test-architecture` (`Makefile:107-108`) therefore runs architecture tests a second time after `arch-test` (`Makefile:86-87`).
- No targets exist for `format`, `pre-commit`, `docker-up`, `docker-down`, `migrate`, or `config-check`.
- `.PHONY` (`Makefile:5`) omits `imports`, `vulture`, `secrets`, `coverage-html`, and `update-deps`.
- `make ci` is `check coverage`, so coverage runs after the same tests have already run.

**Change**

1. Remove the duplicate: keep `arch-test` in `check`, and remove `test-architecture` from the `test` dependency list (or vice versa). Prefer one obvious path:
   - `check: lint typecheck imports vulture secrets test`
   - `test: test-unit test-contract test-architecture test-switches`
2. Make `ci` a single coverage run rather than a second full test run:
   - `ci: lint typecheck imports vulture secrets coverage`
   - Ensure `coverage` includes all suites that should count.
3. Add:
   - `format`: `ruff format src tests` and `ruff check --fix src tests`
   - `pre-commit`: `pre-commit run --all-files`
   - `docker-up`: `docker compose -f docker-compose.test.yml up -d --wait`
   - `docker-down`: `docker compose -f docker-compose.test.yml down -v`
   - `migrate`: `alembic upgrade head`
   - `config-check`: load `config/schema.yaml` and all environment files through the loader
4. Update `.PHONY` and `make help`.
5. Add a `test-security` target after DI-16.

**Acceptance criteria**

- `make check` runs each gate once.
- `make ci` runs tests once with coverage.
- `make help` lists every target that exists.
- No target is missing from `.PHONY`.

**Verify**

```bash
make help
make -n check
make check
```

---

### DI-13 — Commit `.python-version`

**Evidence**

- `.gitignore:81` ignores `.python-version`.
- `pyproject.toml:6` requires `==3.12.*`.
- CI sets `PYTHON_VERSION: "3.12"`.
- No `.python-version` exists in the working tree.
- `actions/setup-python` can read `python-version-file`, but the file is not available.

**Change**

1. Remove `.python-version` from `.gitignore`.
2. Create `.python-version` containing `3.12`.
3. Switch CI and local setup to `python-version-file: .python-version` (or `uv python pin`).
4. Document `uv sync` as the single setup path.

**Acceptance criteria**

- `.python-version` is tracked.
- `uv sync` selects Python 3.12 from the file.
- CI uses the same file, so local and CI cannot drift on Python.

**Verify**

```bash
git ls-files .python-version
uv python find
grep -R "python-version-file" .github/workflows
```

---

## 5. P2 — gates that are weaker than they look

### DI-14 — Complete import-linter contracts

**Evidence**

`pyproject.toml:169-306` currently forbids:

- `domain` → outer layers and vendor libraries.
- `application` → adapters and entrypoints, plus vendor libraries.
- `entrypoints` → adapters.
- `llm`, `embedding`, and `vector_store` adapters → sibling adapters.

Gaps against the direction documented in `CODING_STANDARDS.md`:

- `adapters` can import `application`, `entrypoints`, or `composition`.
- `application` can import `composition`.
- `core` can import anything, including outer layers.
- Only three adapters have sibling-import bans. The other adapters (rerank, readers, repositories, storage, queue, cache, auth, metering) can import each other.
- The vendor bans cover `domain` and `application` but not `core`.

**Change**

1. Add forbidden contracts:
   - `adapters` must not import `application`, `entrypoints`, or `composition`.
   - `application` must not import `composition`.
   - `core` must not import `domain`, `application`, `adapters`, `entrypoints`, or `composition` (core is the shared bottom layer).
2. Replace the three hand-written sibling contracts with an `independence` contract over all adapter modules, or add the missing forbidden pairs. An independence contract is less repetitive and harder to forget.
   - If adapters share a common base module, list it in `ignored_imports` and document why.
3. Add the `core` vendor contract if `core` is meant to stay vendor-light. Note that `core/config`, `core/logging`, and `core/types` may legitimately use Pydantic and OpenTelemetry; make the contract match the documented rule rather than banning everything.
4. Confirm the composition root is the only place allowed to import concrete adapters.
5. Add a test that asserts every top-level package in `src/finsight` is covered by at least one contract, so a new package cannot silently escape.

**Acceptance criteria**

- A deliberate `from finsight.application import ...` inside an adapter fails `lint-imports`.
- A deliberate `from finsight.adapters import ...` inside `core` fails.
- A new adapter cannot import a sibling unless the contract is explicitly updated.
- `make imports` passes on the current tree.

**Verify**

```bash
uv run lint-imports --verbose
# Temporarily add a forbidden import, confirm failure, then revert.
```

---

### DI-15 — Fix dead architecture-test checks

**Evidence**

- `tests/architecture/test_invariants.py:256-260` checks `isinstance(d, ast.Decorator)`. `ast.Decorator` does not exist in the `ast` module, so the property exemption never applies. The intent was to skip `@property` methods; the check should inspect `ast.Name`/`ast.Attribute` decorators.
- `FORBIDDEN_CONSTRUCTORS` (`tests/architecture/test_invariants.py:70`) contains dotted names such as `boto3.client` and `httpx.Client`.
- `get_all_calls` (`tests/architecture/test_invariants.py:114`) returns only the final attribute name (`client`), so the dotted entries never match and direct client construction is not actually blocked.
- The README check (`tests/architecture/test_invariants.py:488`) checks subdirectories but not the root package, which is why `src/finsight/README.md` is missing without failing.

**Change**

1. Fix the property detection:
   - Match `ast.Name` with `id == 'property'` or `ast.Attribute` with `attr == 'property'`.
   - Add a unit test for the helper, not just for the whole suite.
2. Fix call-name extraction:
   - Return fully qualified dotted names (`boto3.client`, `httpx.Client`) from `get_all_calls`, or store only the final names in `FORBIDDEN_CONSTRUCTORS`.
   - Prefer dotted names because they are precise and readable.
3. Extend `test_all_folders_have_readme` to include `src/finsight/README.md`.
4. Add a regression test that intentionally violates each rule in a temporary fixture and asserts failure. Architecture tests that cannot fail are worse than no tests.
5. Run `make arch-test` and fix any real violations the repaired checks expose.

**Acceptance criteria**

- Adding `@property` to a data method exempts it from the `company_id` check.
- Adding `boto3.client(...)` to an adapter fails `test_no_direct_client_construction`.
- Removing `src/finsight/README.md` fails the README test.
- Each repaired check has a test proving it can fail.

**Verify**

```bash
uv run pytest tests/architecture -v -m architecture
uv run pytest tests/architecture -v -m architecture --tb=short
```

---

### DI-16 — Replace the `security-tests` name filter

**Evidence**

- `.github/workflows/ci.yml:281-282` runs:
  `pytest tests/unit -v --tb=short -k "security or company_filter or cache_key or metering or citation"`
- That is a name filter over unit tests, not a security suite.
- Today it mostly selects skipped metering switch tests, so the job can pass while testing almost nothing.
- `pyproject.toml` has no `security` marker.

**Change**

1. Add a `security` marker to `pyproject.toml` and `tests/conftest.py` directory mapping for `tests/security/`.
2. Create `tests/security/` with real tests for:
   - Company isolation: every data method requires and applies `company_id`.
   - Cache keys include `company_id`.
   - Permission matrix enforcement (admin/manager/analyst/viewer).
   - Citation/evidence checks cannot be bypassed.
   - PII handling and log redaction.
   - Prompt-injection detection paths, if implemented.
3. Run `pytest tests/security -m security` in CI.
4. Until the tests exist, make the CI job explicitly pending (skip with a visible message) rather than green-by-accident.
5. Add the job to the `Summary` required list once it has real tests.

**Acceptance criteria**

- The security job fails when a company-isolation test fails.
- The job no longer depends on a `-k` substring filter over unrelated unit tests.
- The marker is documented in `pyproject.toml` and `tests/README.md` (if present).

**Verify**

```bash
uv run pytest tests/security -v -m security
grep -R "tests/security" .github/workflows/ci.yml
```

---

### DI-17 — Run mypy through the locked `uv` environment

**Status: implemented.** The mirrored `mypy` and `import-linter` hooks were replaced with `repo: local` hooks that call `uv run mypy src --strict --show-error-codes` and `uv run lint-imports --verbose`, matching `make typecheck` and `make imports`. See section 13 for the failures that forced this change.

**Evidence**

- `.pre-commit-config.yaml:15-27` uses `mirrors-mypy` at `v1.13.0` in an isolated pre-commit environment.
- `uv.lock` resolves mypy `1.20.2`.
- `additional_dependencies` lists only `pydantic`, `types-requests`, `types-PyYAML`, and `python-json-logger`.
- As adapters import FastAPI, SQLAlchemy, boto3, aiobotocore, redis, and OpenTelemetry, the isolated environment will lack stubs and type information and will diverge from CI.
- Ruff happens to match (`0.17.2` in both), but the same drift risk applies.

**Change**

1. Replace the mirrored mypy hook with a local hook that uses the project environment:

```yaml
- repo: local
  hooks:
    - id: mypy
      name: mypy (uv, locked)
      entry: uv run mypy
      args: [--strict, --show-error-codes]
      language: system
      types_or: [python, pyi]
      pass_filenames: false
```

2. Do the same for `import-linter`, `vulture`, and `detect-secrets` if their mirrored versions can drift. At minimum, add a comment explaining which hooks are intentionally isolated and why.
3. Add a CI assertion that pre-commit tool versions and `uv.lock` versions agree, or rely on local hooks so there is only one environment.
4. Keep `ruff-pre-commit` if the version pin is updated in lockstep; otherwise make it local too.

**Acceptance criteria**

- `pre-commit run mypy --all-files` and `make typecheck` use the same mypy version and dependencies.
- A type error in an adapter fails both paths identically.
- No pre-commit hook silently uses a different major version than the lockfile.

**Verify**

```bash
pre-commit run mypy --all-files
uv run mypy --version
make typecheck
```

---

### DI-18 — Align detect-secrets scope

**Evidence**

- `.pre-commit-config.yaml:47-52` runs `detect-secrets` with `exclude: ^tests/`.
- `Makefile:80-81` runs `detect-secrets-hook` over `git ls-files -co --exclude-standard`, which includes tests.
- CI's pre-commit job (once added) and `make secrets` therefore disagree about the scanned file set.

**Change**

1. Prefer scanning tests too: remove `exclude: ^tests/` from the pre-commit hook. Test fixtures can contain credentials.
2. If tests must be excluded for false positives, exclude only the specific fixture directory and document why.
3. Regenerate `.secrets.baseline` after the scope change:
   - `detect-secrets scan --baseline .secrets.baseline`
   - Review every new entry; do not blindly accept real secrets.
4. Make `make secrets` and pre-commit call the same command shape.

**Acceptance criteria**

- The same file set is scanned by pre-commit, `make secrets`, and CI.
- A dummy secret added under `tests/` is detected.
- The baseline contains only reviewed false positives.

**Verify**

```bash
pre-commit run detect-secrets --all-files
make secrets
```

---

### DI-19 — Align the CI `uv` version with the lockfile

**Evidence**

- `.github/workflows/ci.yml:11` pins `UV_VERSION: "0.5.0"`.
- The local toolchain is `uv 0.13.0`.
- `uv.lock` uses lockfile revision 5 and was generated by a newer `uv`.
- `uv 0.5.0` can export the current lockfile (verified during review), so this is not currently fatal, but it is unnecessary drift and will eventually break on lockfile features.

**Change**

1. Pin `UV_VERSION` to a current version (for example `0.13.0`), or use `astral-sh/setup-uv` with `version-file` if one is introduced.
2. Add a short comment explaining that the version is pinned for reproducibility.
3. Test `uv sync --frozen --all-extras` with the pinned version in CI.
4. Keep local `uv` on the same minor version; document the upgrade procedure in `CONTRIBUTING.md`.

**Acceptance criteria**

- CI and local `uv` versions match.
- `uv sync --frozen` succeeds with the pinned version.
- A lockfile regeneration is a deliberate, reviewed change.

**Verify**

```bash
uv --version
grep -n "UV_VERSION" .github/workflows/ci.yml
uv lock --check
```

---

## 6. P3 — production and deployment infrastructure

### DI-20 — Add infrastructure as code

**Evidence**

- `infra/` contains only `README.md`, `localstack/init.sh`, `postgres/init.sql`, and `otel/collector.yaml`.
- `infra/README.md` promises CDK/Terraform/Pulumi stacks for Aurora, pgvector, DynamoDB, S3, SQS, Lambda, Step Functions, Cognito, IAM, VPC, and CloudWatch.
- None of those stacks exist.

**Change**

1. Choose one tool and record the decision as an ADR:
   - AWS CDK in Python (recommended: same language as the application, typed constructs, good Lambda/Step Functions support).
   - Terraform (recommended if the team already runs it).
2. Add stacks in dependency order:
   - Network: VPC, subnets, security groups.
   - Data: Aurora PostgreSQL with pgvector, DynamoDB tables, S3 buckets.
   - Messaging: SQS queues and dead-letter queues.
   - Auth: Cognito user pool and app client.
   - Compute: Lambda functions, IAM roles, Step Functions.
   - Observability: CloudWatch dashboards, alarms, log groups.
3. Parameterize every environment (dev/staging/prod) from config; no hardcoded account IDs, regions, or resource names.
4. Add `cdk synth` (or `terraform validate`/`plan`) to CI as a non-deploying check.
5. Add snapshot or policy tests for the synthesized templates.

**Acceptance criteria**

- `cdk synth` (or `terraform validate`) succeeds for every environment.
- The synthesized template contains Aurora with pgvector, the S3 buckets, SQS queues, DynamoDB tables, Cognito, and IAM roles named in `infra/README.md`.
- No secret is committed; secrets are referenced from Secrets Manager or SSM.
- CI runs the synth/validate check on every PR.

**Verify**

```bash
cd infra && cdk synth --all
# or: terraform -chdir=infra validate
```

---

### DI-21 — Add container and Lambda packaging

**Evidence**

- README says the backend is deployed as AWS Lambda zip packages (`README.md:7`).
- There is no `Dockerfile`, no `.dockerignore`, and no packaging script.
- `docker-compose.test.yml` is only a test stack; it does not build the application.

**Change**

1. Add a multi-stage `Dockerfile` for local/container deployment:
   - Build stage using `uv`.
   - Runtime stage using a slim Python 3.12 image.
   - Non-root user.
   - Health check if the API entrypoint exists.
2. Add `.dockerignore` (exclude `.git`, `.venv`, caches, tests, docs, build artifacts).
3. Add a Lambda packaging script (for example `scripts/build_lambda.py`) that:
   - Builds a zip for each function.
   - Excludes tests and dev dependencies.
   - Produces deterministic output and a checksum.
4. Add a CI `build-check` step that builds the wheel, the container image (without pushing), and the Lambda zip.
5. Document local container usage in `README.md`.

**Acceptance criteria**

- `docker build .` succeeds.
- The image runs the API (once an entrypoint exists) and responds to a health check.
- The Lambda zip contains only runtime dependencies and application code.
- CI builds all artifacts on every PR.

**Verify**

```bash
docker build -t finsight-ai:local .
uv run python scripts/build_lambda.py --output dist/lambda
unzip -l dist/lambda/api.zip | head
```

---

### DI-22 — Add deploy, release, and rollback workflow

**Evidence**

- No `.github/workflows/deploy.yml`.
- No GitHub Environments or environment-scoped secrets.
- No release/tag workflow.
- No rollback or runbook documentation.
- `docs/README.md` promises a deployment guide; it does not exist.

**Change**

1. Add `.github/workflows/deploy.yml`:
   - Trigger on version tags and/or manual dispatch.
   - Use GitHub OIDC to assume an AWS role; no long-lived AWS keys.
   - Define `dev`, `staging`, and `production` GitHub Environments.
   - Require manual approval for `production`.
   - Deploy the Lambda zip or container image produced by DI-21.
2. Add a release workflow:
   - Tag `vX.Y.Z`.
   - Generate release notes from PRs.
   - Attach build artifacts and checksums.
3. Document rollback:
   - Lambda: redeploy the previous published version or shift the alias.
   - Database: forward-only migrations plus a documented restore path; do not rely on `downgrade` in production.
   - Container: redeploy the previous image digest.
4. Add `docs/deployment.md` and `docs/runbook.md`, or remove the promise from `docs/README.md`.
5. Add a smoke test after deploy (health endpoint, one read-only check).

**Acceptance criteria**

- A tag deploy to `dev` completes without long-lived AWS credentials.
- Production deploy requires an approved environment.
- The rollback procedure is documented and has been exercised at least once in staging.
- Release notes and artifacts are attached to the tag.

**Verify**

```bash
gh workflow list
gh release list
gh api repos/sah-automation/finsight-AI/environments
```

---

## 7. Documentation and repository hygiene

### DI-23 — Fix README and documentation gaps

**Evidence**

- `README.md:177` links `docs/plans/Project Requirement/finsight_config_switches.md`. The actual path is `docs/plans/project_requirement/finsight_config_switches.md` (lowercase, underscore).
- `README.md:186` links `docs/plans/Project Requirement/FinSightAI.md`. The actual file is `docs/plans/project_requirement/finsightAI.md`.
- `README.md:188` says ADRs are "to be created", but `docs/adr/0001-standards-enforcement.md` exists.
- `README.md:189` says `GLOSSARY.md` is "to be created"; per `docs/agents/domain.md`, it should be created lazily rather than promised. Either create it or remove the claim.
- `README.md:49` uses `uv run uvicorn src.finsight.entrypoints.api.main:app --reload`. The package is installed as `finsight`, so the path should be `finsight.entrypoints.api.main:app` (once that entrypoint exists).
- `src/finsight/README.md` is missing. The architecture test checks subdirectories only, so the gap is invisible.
- `docs/README.md` promises a deployment guide and developer onboarding; neither exists.
- No `CONTRIBUTING.md`, `LICENSE`, or `.editorconfig`.

**Change**

1. Fix the three broken links and the capitalization.
2. Remove "to be created" for ADRs; link the existing ADR.
3. Either add `GLOSSARY.md` with the handful of terms already used, or remove the line and let it be created lazily.
4. Fix the uvicorn module path; if the entrypoint does not exist yet, mark the command as "when implemented" instead of showing a broken path.
5. Add `src/finsight/README.md` describing the package root and layer map.
6. Add `CONTRIBUTING.md`:
   - Setup (`uv sync`, `make install-hooks`).
   - Branch/PR rules and required checks.
   - How to run each suite.
   - How to add a config switch and both test paths.
   - How to run migrations.
   - Commit message convention.
7. Add `.editorconfig` (UTF-8, LF, final newline, 4-space Python, 2-space YAML).
8. Add `LICENSE` per DI-03.
9. Add `docs/deployment.md` and `docs/onboarding.md`, or edit `docs/README.md` so it no longer promises files that do not exist.
10. Add a link checker to CI (for example `lychee`) or a simple script that verifies relative Markdown links.

**Acceptance criteria**

- Every relative link in `README.md` and `docs/README.md` resolves.
- `uv run uvicorn finsight...` is the documented path.
- A new contributor can follow `CONTRIBUTING.md` end to end.
- No document promises a file that does not exist.

**Verify**

```bash
# Example link check; replace with the chosen tool.
uvx lychee README.md docs/README.md docs/plans/*.md
```

---

### DI-24 — Resolve unused config files and missing root docs

**Evidence**

- `config/permissions.yaml` and `config/prices.yaml` exist and are described in `config/README.md`.
- A search of `src/` finds no code that reads either file. Only adapter READMEs mention them.
- `docs/agents/domain.md` expects `GLOSSARY.md` and `docs/adr/`, but `GLOSSARY.md` does not exist (lazy creation is acceptable per that document).
- `docs/plans/quality-standards-enforcement.md` describes gates that are not all implemented (pre-commit in CI, coverage ratchet).

**Change**

1. Decide for each unused config file:
   - **Consume it:** add typed models and loaders in `core/config`, with tests, so permissions and prices are not silently ignored.
   - **Mark it planned:** add a `status: planned` comment and a tracking issue, and remove it from any documentation that implies it is active.
2. Do not leave a config file that looks authoritative but is never read.
3. Add `GLOSSARY.md` with the terms already used in `CODING_STANDARDS.md` and `finsightAI.md` (company, document, chunk, metric, answer, citation, role, switch) or remove the README promise.
4. Update `docs/plans/quality-standards-enforcement.md` to distinguish implemented gates from planned ones. Link this plan instead of duplicating status.
5. Add a `config-check` test that loads every environment file through the loader and asserts the schema validates.

**Acceptance criteria**

- Every file under `config/` is either read by code or explicitly marked planned with a tracking issue.
- `config-check` passes for `development`, `test`, `staging`, and `production` with the required env vars supplied.
- Status docs match reality.

**Verify**

```bash
grep -R "permissions.yaml\|prices.yaml" src tests
make config-check
```

---

## 8. Protect requirement and architecture documents (DI-25)

**Requirement:** `docs/plans/project_requirement/` and `docs/plans/architecture/` must not be editable without an explicit permission prompt.

### Why OpenCode permissions, not only `chmod`

- `chmod` makes files read-only at the OS level, but an agent or developer can `chmod` them back. It also complicates legitimate updates.
- OpenCode's `edit` permission covers the `edit`, `write`, and `patch` tools and can prompt before any modification.
- A project-level config applies to every agent session started in this repository, including subagents, without relying on each person's global config.

### Change

Add `opencode.json` at the repository root:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "permissions": [
    {
      "action": "edit",
      "resource": "*docs/plans/project_requirement/**",
      "effect": "ask"
    },
    {
      "action": "edit",
      "resource": "*docs/plans/architecture/**",
      "effect": "ask"
    },
    {
      "action": "write",
      "resource": "*docs/plans/project_requirement/**",
      "effect": "ask"
    },
    {
      "action": "write",
      "resource": "*docs/plans/architecture/**",
      "effect": "ask"
    },
    {
      "action": "bash",
      "resource": "*docs/plans/project_requirement*",
      "effect": "ask"
    },
    {
      "action": "bash",
      "resource": "*docs/plans/architecture*",
      "effect": "ask"
    }
  ]
}
```

Notes:

- `edit` is the primary control; `write` is included explicitly because the tool exists separately.
- The leading `*` in each resource pattern matches both repository-relative paths and absolute paths.
- The `bash` rules catch shell commands that reference the protected directories (for example `sed -i`, `rm`, `mv`, `cp`, or redirection). They are defense-in-depth, not a sandbox: a command that changes directory first and then edits a bare filename can still bypass a path substring match.
- Reads remain allowed. The goal is to prevent silent modification, not to hide the documents.
- Do not use `"effect": "deny"`; the requirement is to ask, not to make legitimate updates impossible.
- Keep this file committed so the protection travels with the repository.

### Optional hardening

- Add a filesystem-level guard in CI that fails if either directory changes without a matching approval label or CODEOWNERS review.
- Add both directories to `.github/CODEOWNERS` so GitHub also requires a reviewer.
- Add a pre-commit hook that rejects changes under these paths unless `ALLOW_PROTECTED_DOCS=1` is set. This is optional and can be noisy; prefer the OpenCode prompt plus CODEOWNERS.

### Acceptance criteria

- Editing `docs/plans/project_requirement/finsightAI.md` through the `edit` tool prompts for approval.
- Creating or overwriting a file under `docs/plans/architecture/` prompts for approval.
- A `bash` command containing either directory path prompts for approval.
- Editing a normal file such as `README.md` does not prompt because of these rules.
- Reading the protected files does not prompt.
- The config validates against `https://opencode.ai/config.json`.

### Verify

```bash
# Config parses and is picked up as a project config source.
opencode debug config

# JSON validity and rule shape.
python3 - <<'PY'
import json
cfg = json.load(open('opencode.json'))
assert cfg['$schema'] == 'https://opencode.ai/config.json'
for rule in cfg['permissions']:
    assert set(rule) == {'action', 'resource', 'effect'}
    assert rule['effect'] in {'allow', 'ask', 'deny'}
print(f"{len(cfg['permissions'])} permission rules valid")
PY
```

Then attempt a harmless edit to a protected file in a scratch branch and confirm the prompt appears before any write.

---

## 9. Execution order

### Milestone 0 — Make CI trustworthy (P0)

1. DI-03: decide visibility/license.
2. DI-02: remove `cache: uv`.
3. DI-01: push `main`, let CI run once, then add branch protection.
4. DI-04: install hooks and fix `commit-msg`.
5. DI-05: reconcile local/test configuration.
6. DI-06: add `.env.example`.
7. DI-25: add `opencode.json` protection.

Exit criteria: a pull request from a branch runs the full CI workflow, `Summary` is meaningful, and local integration tests can start the stack.

### Milestone 1 — Close the promised gates (P1)

1. DI-08: pre-commit CI job.
2. DI-12: Makefile cleanup.
3. DI-13: `.python-version`.
4. DI-07: Alembic skeleton and initial migration.
5. DI-09: coverage floor and ratchet.
6. DI-10 + DI-11: Dependabot, audit, templates, CODEOWNERS.

Exit criteria: every gate named in `docs/plans/quality-standards-enforcement.md` either runs in CI or is explicitly marked planned.

### Milestone 2 — Make the gates honest (P2)

1. DI-17: mypy through `uv`.
2. DI-18: detect-secrets scope.
3. DI-15: architecture-test fixes.
4. DI-14: import-linter contracts.
5. DI-16: real security tests.
6. DI-19: `uv` version alignment.

Exit criteria: deliberately violating an architecture or security rule fails locally and in CI.

### Milestone 3 — Deployment scaffolding (P3)

1. DI-20: IaC choice ADR and first stacks.
2. DI-21: Dockerfile and Lambda packaging.
3. DI-22: deploy/release/rollback.
4. DI-23 + DI-24: documentation and config cleanup.

Exit criteria: a tag can deploy to `dev` with OIDC, production requires approval, and rollback is documented and exercised.

---

## 10. Verification matrix

| Gate | Local command | CI job | Fails on |
| --- | --- | --- | --- |
| Style | `make lint` | `lint-and-typecheck` | ruff violations |
| Types | `make typecheck` | `lint-and-typecheck` | mypy errors |
| Imports | `make imports` | `lint-and-typecheck` | contract violation |
| Dead code | `make vulture` | `lint-and-typecheck` | unused code |
| Secrets | `make secrets` | `pre-commit` | unbaselined secret |
| YAML/shell/hygiene | `make pre-commit` | `pre-commit` | malformed YAML, shellcheck, large file |
| Architecture | `make arch-test` | `architecture-tests` | invariant violation |
| Unit | `make test-unit` | `unit-tests` | test failure |
| Contract | `make test-contract` | `contract-tests` | test failure |
| Switches | `make test-switches` | `switch-tests` | missing ON/OFF path |
| Integration | `make test-integration` | `integration-tests` | service/config failure |
| Golden | `make test-golden` | `golden-tests` | quality regression |
| Security | `make test-security` | `security-tests` | isolation/permission failure |
| Coverage | `make ci` | `unit-tests` / coverage step | below floor |
| Dependencies | `uvx pip-audit` | `dependency-audit` | vulnerable dependency |
| Packaging | `docker build .` / `uv build` | `build-check` | build failure |
| IaC | `cdk synth --all` | `infra-synth` | invalid template |
| Docs | `lychee ...` | `docs` (optional) | broken link |

Document any job that is intentionally skipped, and make the skip visible in `Summary`.

---

## 11. Risks, assumptions, and notes

- **The compose stack was exercised on a machine with Docker (Colima).** The original static review could not run it. DI-05 and DI-07 are now verified end to end; the OTel image pin and the obsolete Compose `version` key were both wrong and are fixed.
- **The full local test suite passes but most tests are skipped.** A fresh run reports 41 passed, 22 skipped and 52.18% line coverage. The skips are real gaps (no adapters, no golden set, stub switches), not environment failures. Re-baseline before setting the DI-09 floor.
- **The repository has never been pushed.** GitHub-side settings (rulesets, environments, secrets, Actions permissions) cannot be verified until DI-01.
- **Changing `Environment` to add `TEST` touches application-layer config models.** Keep the change minimal: add the enum value, add `config/test.yaml`, and update loader tests. Do not change production validation behavior.
- **Import-linter independence contracts can be noisy** if adapters share base classes or DTOs. Start with forbidden contracts, then move to independence where it is clean.
- **Coverage floors can encourage gaming.** Raise the floor only when the added tests assert behavior, not when they merely execute lines.
- **OpenCode permissions are a guardrail, not a security boundary.** A shell command that changes directory and then edits a bare filename can bypass a path substring rule. CODEOWNERS and review remain the hard gate for the requirement and architecture documents.
- **Do not commit real secrets** while adding `.env.example`, Dependabot, or deploy workflows. Use GitHub Environments and OIDC.

---

## 12. Definition of done for this plan

- `origin/main` exists, CI has run, and `main` is protected by required checks.
- All P0 items are closed.
- Every P1 item is closed or explicitly deferred with a linked issue and a reason.
- P2 gates can fail when deliberately violated and have regression tests proving it.
- The requirement and architecture directories prompt before edits in every OpenCode session in this repository.
- `README.md`, `CONTRIBUTING.md`, and `docs/README.md` agree with the actual repository layout.
- A new contributor can go from clone to `make check` using only the committed documentation and `.env.example`.

---

## 13. Execution log

This section records what happened when the stack and gates were actually run, after the static review above. It exists so later workstreams do not rediscover the same failures.

### 13.1 Environment

| Item | Value |
| --- | --- |
| Host | macOS 26.6, arm64, 10 CPU, 16 GB RAM |
| Docker runtime | Colima 0.10.3 (lima 2.2.1), `vz` driver, `virtiofs` mounts |
| Docker CLI | 29.9.0, server 29.5.2 |
| Docker Compose | 5.6.0 |
| VM resources | 4 CPU, 8 GB RAM, 60 GB disk |

- Docker was not installed. It was installed with Homebrew, not Docker Desktop.
- The Homebrew `docker-compose` formula installs the plugin outside the default CLI plugin path. `docker compose` only worked after adding `/opt/homebrew/lib/docker/cli-plugins` to `cliPluginsExtraDirs` in `~/.docker/config.json`. Record this in `CONTRIBUTING.md` under DI-23.

### 13.2 New findings from running the stack

These were not visible in the static review.

1. `docker-compose.test.yml` still declared `version: '3.8'`, which Compose warns is obsolete. Removed.
2. `otel/opentelemetry-collector-contrib:0.115.0` **does not exist** (Docker Hub returns 404). The next published tag, `0.116.0`, has an arm64 manifest but the arm64 image is broken: it exits 255 with `exec /otelcol-contrib: no such file or directory`. The binary is missing from the image. Pinned `0.120.0` instead, which starts and reports `0.120.1`.
3. With `0.120.0`, all four services reached `healthy` and stayed up.

Verified against the running stack from the host, not only inside containers:

| Check | Result |
| --- | --- |
| S3 buckets | `backups`, `documents`, `reports` |
| SQS queues | `dlq`, `ingestion`, `reports`, `reprocessing` |
| DynamoDB tables | `answer_cache`, `metering`, `role_cache` |
| pgvector | `0.8.7` |
| Redis | `PING` → `True` |
| OTLP gRPC/HTTP | ports `4317` and `4318` open |

This closes the "stack was inspected statically, not exercised" risk for the compose file and the LocalStack/Postgres bootstrap. It does not close DI-05: `config/dev.yaml` still disagrees with the stack (database name, bucket/queue/table prefixes, endpoint).

### 13.3 Gate results

| Command | Result |
| --- | --- |
| `make check` | Passed: ruff, `ruff format --check`, mypy (39 files), 8 import-linter contracts, vulture, detect-secrets, 29 architecture tests (1 skipped), 12 unit tests (20 skipped), 1 contract test skipped, 3 switch tests (20 skipped) |
| `make test-integration` | 1 skipped: "No adapters implemented yet" |
| `make test-golden` | 1 skipped: "No golden question set yet" |
| `make coverage` | 41 passed, 22 skipped, **52.18%** line coverage |
| CI `security-tests` filter | 4 tests selected, **all skipped** |
| `uv run pre-commit run --all-files` | 18 hooks pass after the fixes below |

Confirmations of existing findings:

- `make check` runs the architecture tests twice: once via `arch-test` and once inside `test`. This is the DI-12 duplicate-work finding, now observed.
- `fail_under = 0` means `make coverage` can never fail on coverage. DI-09 is still open.
- The security job's `-k "security or company_filter or cache_key or metering or citation"` selects only tests that are skipped. DI-16 is still open and is worse than a naming problem: the job reports success while testing nothing.
- The verification matrix in section 10 references `make pre-commit` and `make test-security`. Neither target exists in the `Makefile`. Add them under DI-12 or fix the matrix.

### 13.4 Pre-commit findings

Pre-commit could not run at all as configured. Four separate faults:

1. `seddonym/import-linter` was pinned to `1.12.1`, but the repository only tags `v1.12.1`. Pre-commit failed while initializing the environment, before running any hook.
2. `vulture/vulture` no longer serves the hook manifest. The maintained repository is `jendrikseipp/vulture`; `v2.10` was also stale and was moved to `v2.16`.
3. The mirrored mypy hook ran in an isolated environment with only four `additional_dependencies`, so it could not import `pytest` and could not see the project package. It produced 56 errors in 18 files, all environmental rather than real type errors.
4. The mirrored import-linter hook failed with `Could not find package 'finsight' in your Python path.`

Yamllint, run for the first time, reported two real errors:

- `.pre-commit-config.yaml` lines 22–25: `additional_dependencies` indented 12 spaces where 10 are expected. Removed with the hook rewrite.
- `.github/workflows/ci.yml` line 3: `on:` is parsed as a boolean by YAML 1.1 and trips the `truthy` rule. Quoted as `"on":`, which GitHub Actions accepts. The 155-character `needs:` list on line 315 was also wrapped to a block sequence.

### 13.5 Changes made during execution

| File | Change |
| --- | --- |
| `docker-compose.test.yml` | Removed obsolete `version`; pinned OTel `0.120.0` |
| `.pre-commit-config.yaml` | Fixed import-linter rev; fixed vulture repo/rev; replaced the mypy and import-linter hooks with local `uv run` hooks (DI-17) |
| `.github/workflows/ci.yml` | Quoted `"on":`; wrapped the `needs` list |
| ~60 files | Trailing newline added by `end-of-file-fixer` (whitespace only) |
| `opencode.json` | Added (DI-25) |
| `docs/plans/dev-infra-implementation-plan.md` | This plan |

Note on the protected documents: `end-of-file-fixer` added a trailing newline to `docs/plans/project_requirement/finsightAI.md` and `docs/plans/architecture/phase1/finsight_mvp_hld.svg`. That was a formatter run, not a content edit, and it is the only reason those files appear in `git status`. Review them before committing; revert if even whitespace changes to those paths require sign-off.

The local mypy hook checks `src` only, to match `make typecheck`. Type-checking `tests` in an isolated hook environment is what produced the 56 false errors, and the project's own gate does not check tests. If test type-checking is wanted, add it as a separate workstream with the project environment, not by widening this hook.

### 13.6 What this execution did not close

Every open item in section 2 is still open except DI-04, DI-17 and DI-25, and DI-04 is only partly done: hooks were not installed into `.git/hooks` and no `commit-msg` hook was added.

The most important still-open items after this pass:

- DI-01/02/03: nothing was pushed, CI has still never run, and the public-repo/proprietary-license conflict is unresolved.
- DI-05/06: no `config/test.yaml`, no `.env.example`, and `config/dev.yaml` still does not match the compose stack.
- DI-08: pre-commit is not run in CI, so all 18 hooks are still local-only.
- DI-09: coverage floor is `0`.
- DI-16: the security job tests nothing.

---

## 14. P0 execution log (2026-10-26)

P0 was implemented on `main` in commit `395c63a` (the pushed commit) and
verified against GitHub and the local Docker stack. The first `main` CI run
(`40231109458`) passed every job, including `Summary`. P1 and later items
remain open unless section 13 already marks them implemented.

| ID | Status | Evidence |
| --- | --- | --- |
| DI-01 | Done | `origin/main` points at `395c63a`. The repository is still `PUBLIC`. Ruleset `Protect main` (ID `25836226`) requires a pull request, the `Summary` check, an up-to-date branch, and conversation resolution; it blocks force pushes and deletion, and has no bypass actors. |
| DI-02 | Done | `grep -R "cache: uv" .github/workflows` returns nothing. `enable-cache: true` remains on `astral-sh/setup-uv` in every job. |
| DI-03 | Done | Keep-public option applied: Apache-2.0 `LICENSE` added, `README.md` links it, and `pyproject.toml` declares `license = {text = "Apache-2.0"}`. The built wheel includes `dist-info/licenses/LICENSE`. |
| DI-04 | Done | `conventional-pre-commit` `v4.4.0` is wired at the `commit-msg` stage. `default_install_hook_types` installs both hooks; `.git/hooks/pre-commit` and `.git/hooks/commit-msg` are executable. A non-conventional message fails and a conventional message passes. `pre-commit run --all-files` passes. |
| DI-05 | Done | `Environment.TEST` and `config/test.yaml` exist. Test values match `docker-compose.test.yml` and `infra/localstack/init.sh` (database `test`/`test`, buckets `documents`/`reports`/`backups`, queues `ingestion`/`reprocessing`/`reports`/`dlq`, tables `answer_cache`/`role_cache`/`metering`). CI integration uses `ENVIRONMENT=test`, dummy AWS credentials, `AWS_ENDPOINT_URL`, and `docker compose ... up -d --wait`. `make test-integration` selects the test profile. |
| DI-06 | Done | `.env.example` exists with grouped, commented, safe placeholders; it is not gitignored; `detect-secrets` passes; `README.md` references it and explains that it targets the test profile. |
| DI-25 | Done | `opencode.json` is committed. Its six `edit`/`write`/`bash` rules validate against the documented shape, and the protected paths are `docs/plans/project_requirement/**` and `docs/plans/architecture/**`. |

Verification run during this pass:

```bash
ENVIRONMENT=test uv run python -c "from finsight.core.config import load_config; c=load_config(); print(c.app.environment, c.storage.documents_bucket)"
uv run pre-commit run --all-files
make check
make test-integration
docker compose -f docker-compose.test.yml up -d --wait
docker compose -f docker-compose.test.yml down -v
```

The local stack reached `healthy` for all four services and created the S3,
SQS, and DynamoDB resources listed above. The integration suite remains a
placeholder skip until adapters exist; the configuration path itself is
verified by `tests/unit/core/config/test_loader.py`.
