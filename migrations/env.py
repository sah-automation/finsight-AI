"""Alembic environment for FinSight AI.

The database URL comes from `finsight.core.config` so migrations use the same
profile, host, credentials, and SSL mode as the application. There is no
`sqlalchemy.url` in `alembic.ini` and no database URL hard-coded here.

Usage:
    ENVIRONMENT=test uv run alembic upgrade head
    uv run alembic current

`target_metadata` stays `None` until SQLAlchemy models exist in
`adapters/repositories`. The initial migration is hand-written SQL, so
`alembic check` (model drift) is deliberately not enabled yet.
"""

from __future__ import annotations

import os
from logging.config import fileConfig
from urllib.parse import quote_plus

from alembic import context
from sqlalchemy import engine_from_config, pool

# Try to import the config loader; if it fails (e.g., during migration when
# only VECTOR_DB_* env vars are set), fall back to VECTOR_DB_* env vars.
try:
    from finsight.core.config import load_config
except Exception:
    load_config = None  # type: ignore[assignment]

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _database_url() -> str:
    """Build a synchronous psycopg URL from the validated app config or VECTOR_DB_* env vars."""
    # First try to use the full app config (preferred when all env vars are set)
    if load_config is not None:
        try:
            vector_store = load_config().vector_store
            username = quote_plus(vector_store.username)
            password = quote_plus(vector_store.password)
            return (
                f'postgresql+psycopg://{username}:{password}'
                f'@{vector_store.host}:{vector_store.port}/{vector_store.database}'
                f'?sslmode={vector_store.ssl_mode}'
            )
        except Exception:
            # Fall through to VECTOR_DB_* env vars fallback
            pass

    # Fallback: build URL from VECTOR_DB_* env vars (set by migration script)
    host = os.getenv('VECTOR_DB_HOST')
    port = os.getenv('VECTOR_DB_PORT')
    database = os.getenv('VECTOR_DB_NAME')
    username = os.getenv('VECTOR_DB_USER')
    password = os.getenv('VECTOR_DB_PASSWORD')
    ssl_mode = os.getenv('VECTOR_DB_SSLMODE', 'require')

    if not all([host, port, database, username, password]):
        raise RuntimeError(
            'Cannot build database URL: neither full config nor VECTOR_DB_* env vars are available'
        )

    return (
        f'postgresql+psycopg://{quote_plus(username)}:{quote_plus(password)}'
        f'@{host}:{port}/{database}?sslmode={ssl_mode}'
    )


def run_migrations_offline() -> None:
    """Run migrations without a live database connection."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the configured database."""
    section = config.get_section(config.config_ini_section, {})
    section['sqlalchemy.url'] = _database_url()
    connectable = engine_from_config(section, prefix='sqlalchemy.', poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
