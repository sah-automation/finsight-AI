# Multi-stage Dockerfile for FinSight AI.
# This image is a deployment scaffold: no API entrypoint exists yet, so the
# default command only proves the runtime environment imports the package.
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Keep the builder uv version aligned with UV_VERSION in .github/workflows/ci.yml.
RUN pip install --no-cache-dir uv==0.13.0

WORKDIR /app

# The package must be installable before `uv sync` runs, so copy the build
# inputs first. README.md is referenced by pyproject.toml.
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ ./src/

# --no-editable installs the project into .venv, so the runtime stage does not
# need the source tree.
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY config/ ./config/
COPY migrations/ ./migrations/
COPY alembic.ini ./

USER appuser

CMD ["python", "-c", "import finsight; print('FinSight AI container ready')"]
