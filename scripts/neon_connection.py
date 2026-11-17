"""Neon connection-string parsing shared by the deploy scripts.

Both ``run_migration.py`` (Alembic gate) and ``sync_lambda_env.py``
(post-deploy env injection) decompose the same SSM-stored
``postgresql://`` URL into the ``VECTOR_DB_*`` variables the config
loader expects. Keeping the parser in one module guarantees both
entrypoints always agree on the decomposition.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote, urlparse


@dataclass(frozen=True)
class VectorDbConfig:
    """Vector database connection configuration."""

    host: str
    port: int
    database: str
    username: str
    password: str
    sslmode: str


def parse_database_url(url: str) -> VectorDbConfig:
    """Parse a PostgreSQL connection URL into a VectorDbConfig.

    Expected format: postgresql://user:pwd@host:port/db?sslmode=require # pragma: allowlist secret
    """
    parsed = urlparse(url)
    if parsed.scheme not in ('postgresql', 'postgres'):
        raise ValueError(f'Expected postgresql:// URL, got {parsed.scheme}://')

    # Extract password (may contain special chars) and decode URL encoding
    password = unquote(parsed.password or '')

    # Parse query parameters for sslmode
    sslmode = 'require'
    if parsed.query:
        query_params = dict(q.split('=') for q in parsed.query.split('&') if '=' in q)
        sslmode = query_params.get('sslmode', 'require')

    return VectorDbConfig(
        host=parsed.hostname or '',
        port=parsed.port or 5432,
        database=parsed.path.lstrip('/') if parsed.path else '',
        username=parsed.username or '',
        password=password,
        sslmode=sslmode,
    )


def build_vector_db_env(config: VectorDbConfig) -> dict[str, str]:
    """Build VECTOR_DB_* environment variables dict for the config loader."""
    return {
        'VECTOR_DB_HOST': config.host,
        'VECTOR_DB_PORT': str(config.port),
        'VECTOR_DB_NAME': config.database,
        'VECTOR_DB_USER': config.username,
        'VECTOR_DB_PASSWORD': config.password,
        'VECTOR_DB_SSLMODE': config.sslmode,
    }
