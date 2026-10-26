# Developer Onboarding

## Prerequisites
- Python 3.12 (pinned in `.python-version`)
- [uv](https://docs.astral.sh/uv/) package manager
- Docker + Docker Compose
- Git

## Setup Steps

1. **Clone repository**
```bash
git clone https://github.com/sah-automation/finsight-AI.git
cd finsight-AI
```

2. **Install dependencies**
```bash
uv sync --frozen --all-extras
```

3. **Configure environment**
```bash
cp .env.example .env
set -a; source .env; set +a
```
The `.env.example` targets the local test profile (`ENVIRONMENT=test`).

4. **Install git hooks**
```bash
make install-hooks
```
This installs pre-commit and commit-msg hooks (Conventional Commits enforced).

5. **Start local services**
```bash
make docker-up
```

6. **Run migrations**
```bash
ENVIRONMENT=test make migrate
```

7. **Verify setup**
```bash
make check
make test
```

## Development Workflow
1. Create a branch
2. Make changes following [CODING_STANDARDS.md](../CODING_STANDARDS.md)
3. Run `make format` and `make check`
4. Commit with conventional commit message
5. Open PR using the template
6. Ensure all CI checks pass

## Useful Commands
- `make help` - list all targets
- `make format` - auto-format code
- `make check` - run all quality gates
- `make test-security` - run security tests
- `make config-check` - validate all config profiles

## Getting Help
- Read [CONTRIBUTING.md](../CONTRIBUTING.md)
- Check [CODING_STANDARDS.md](../CODING_STANDARDS.md)
- Review existing ADRs in `docs/adr/`
