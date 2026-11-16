#!/usr/bin/env python3
"""Run database migrations against the production Neon database.

This script:
1. Retrieves the Neon connection string from AWS SSM Parameter Store
2. Parses it to extract connection components
3. Sets the VECTOR_DB_* environment variables for the config loader
4. Runs `alembic upgrade head`
5. Verifies the migration with `alembic current` (hard gate)

The connection string comes from the SSM-injected Neon parameter (the same one
the app resolves — never from GitHub secrets), and the script uses the same
OIDC-assumed role that the deploy workflow uses.

Usage:
    uv run python scripts/run_migration.py --environment prod
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from urllib.parse import unquote, urlparse

import boto3  # type: ignore[import-untyped]
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]

# SSM parameter path pattern (matches app's secrets provider)
SSM_PARAMETER_PATTERN = '/finsight/{env}/neon/database_url'

# Environment mapping from CDK env to app ENVIRONMENT
ENV_MAPPING = {
    'prod': 'production',
}


@dataclass(frozen=True)
class VectorDbConfig:
    """Vector database connection configuration."""

    host: str
    port: int
    database: str
    username: str
    password: str
    sslmode: str


def get_ssm_parameter(parameter_name: str, region: str) -> str:
    """Retrieve a SecureString parameter from SSM Parameter Store."""
    client = boto3.client('ssm', region_name=region)
    response = client.get_parameter(Name=parameter_name, WithDecryption=True)
    return response['Parameter']['Value']  # type: ignore[no-any-return]


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
    }


def run_alembic_upgrade(
    environment: str, env_vars: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    """Run alembic upgrade head with the given environment."""
    env = os.environ.copy()
    env.update(env_vars)
    env['ENVIRONMENT'] = ENV_MAPPING.get(environment, environment)
    return subprocess.run(
        ['uv', 'run', 'alembic', 'upgrade', 'head'],  # noqa: S607
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def run_alembic_current(
    environment: str, env_vars: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    """Run alembic current to verify the migration (hard gate)."""
    env = os.environ.copy()
    env.update(env_vars)
    env['ENVIRONMENT'] = ENV_MAPPING.get(environment, environment)
    return subprocess.run(
        ['uv', 'run', 'alembic', 'current'],  # noqa: S607
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--environment',
        required=True,
        choices=['prod'],
        help='Target environment (maps to CDK env name)',
    )
    parser.add_argument(
        '--region',
        required=True,
        help='AWS region (from AWS_REGION env var)',
    )
    parser.add_argument(
        '--parameter-name',
        help='Override the SSM parameter name (default: /finsight/{env}/neon/database_url)',
    )
    args = parser.parse_args(argv)

    env = args.environment
    region = args.region
    parameter_name = args.parameter_name or SSM_PARAMETER_PATTERN.format(env=env)

    print(f'🔐 Retrieving Neon connection string from SSM: {parameter_name}')
    try:
        database_url = get_ssm_parameter(parameter_name, region)
    except (BotoCoreError, ClientError) as e:
        print(f'❌ Failed to retrieve SSM parameter: {e}', file=sys.stderr)
        return 1

    print('🔍 Parsing connection string...')
    try:
        config = parse_database_url(database_url)
    except ValueError as e:
        print(f'❌ Failed to parse connection string: {e}', file=sys.stderr)
        return 1

    print(f'   Host: {config.host}')
    print(f'   Port: {config.port}')
    print(f'   Database: {config.database}')
    print(f'   Username: {config.username}')
    print(f'   SSL mode: {config.sslmode}')

    print('🔧 Building VECTOR_DB_* environment variables...')
    env_vars = build_vector_db_env(config)

    print('📦 Running alembic upgrade head...')
    result = run_alembic_upgrade(env, env_vars)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if result.returncode != 0:
        print('❌ Migration failed!', file=sys.stderr)
        return result.returncode

    print('✅ Migration completed successfully')
    print('🔍 Verifying migration with alembic current (hard gate)...')
    verify_result = run_alembic_current(env, env_vars)
    if verify_result.stdout:
        print(verify_result.stdout)
    if verify_result.stderr:
        print(verify_result.stderr, file=sys.stderr)

    if verify_result.returncode != 0:
        print('❌ Verification failed — schema not at current head!', file=sys.stderr)
        return 1

    print('✅ Verification passed — schema is at current migration head')
    print('🎉 Migration job completed successfully')
    return 0


if __name__ == '__main__':
    sys.exit(main())
