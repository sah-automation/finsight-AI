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

from logging.config import fileConfig
from urllib.parse import quote_plus

from alembic import context
from sqlalchemy import engine_from_config, pool

from finsight.core.config import load_config

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _database_url() -> str:
    """Build a synchronous psycopg URL from the validated app config."""
    vector_store = load_config().vector_store
    username = quote_plus(vector_store.username)
    password = quote_plus(vector_store.password)
    return (
        f'postgresql+psycopg://{username}:{password}'
        f'@{vector_store.host}:{vector_store.port}/{vector_store.database}'
        f'?sslmode={vector_store.ssl_mode.value}'
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
