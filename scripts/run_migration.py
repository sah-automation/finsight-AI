#!/usr/bin/env python3
"""Run database migrations against the production Neon database.

This script:
1. Retrieves the Neon connection string from AWS SSM Parameter Store
2. Parses it to extract connection components
3. Sets the VECTOR_DB_* environment variables for the config loader
4. Runs `alembic upgrade head`
5. Verifies the migration with `alembic current`

The connection string comes from the SSM-injected Neon parameter (the same one
the app resolves — never from GitHub secrets), and the script uses the same
OIDC-assumed role that the deploy workflow uses.

Usage:
    uv run python scripts/run_migration.py --environment prod
    uv run python scripts/run_migration.py --environment staging
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from urllib.parse import unquote, urlparse

import boto3  # type: ignore[import-untyped]
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]

# SSM parameter path pattern
SSM_PARAMETER_PATTERN = '/finsight/{env}/neon/database_url'

# Environment mapping from CDK env to app ENVIRONMENT
ENV_MAPPING = {
    'dev': 'development',
    'staging': 'staging',
    'prod': 'production',
}


def get_ssm_parameter(parameter_name: str, region: str) -> str:
    """Retrieve a SecureString parameter from SSM Parameter Store."""
    client = boto3.client('ssm', region_name=region)
    response = client.get_parameter(Name=parameter_name, WithDecryption=True)
    return response['Parameter']['Value']  # type: ignore[no-any-return]


def parse_database_url(url: str) -> dict[str, str]:
    """Parse a PostgreSQL connection URL into components.

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

    return {
        'host': parsed.hostname or '',
        'port': str(parsed.port or 5432),
        'database': parsed.path.lstrip('/') if parsed.path else '',
        'username': parsed.username or '',
        'password': password,
        'sslmode': sslmode,
    }


def set_vector_db_env(components: dict[str, str]) -> None:
    """Set VECTOR_DB_* environment variables for the config loader."""
    os.environ['VECTOR_DB_HOST'] = components['host']
    os.environ['VECTOR_DB_PORT'] = components['port']
    os.environ['VECTOR_DB_NAME'] = components['database']
    os.environ['VECTOR_DB_USER'] = components['username']
    os.environ['VECTOR_DB_PASSWORD'] = components['password']


def run_alembic_upgrade(environment: str) -> subprocess.CompletedProcess[str]:
    """Run alembic upgrade head with the given environment."""
    env = os.environ.copy()
    env['ENVIRONMENT'] = ENV_MAPPING.get(environment, environment)
    return subprocess.run(
        ['uv', 'run', 'alembic', 'upgrade', 'head'],  # noqa: S607
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def run_alembic_current(environment: str) -> subprocess.CompletedProcess[str]:
    """Run alembic current to verify the migration."""
    env = os.environ.copy()
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
        choices=['dev', 'staging', 'prod'],
        help='Target environment (maps to CDK env name)',
    )
    parser.add_argument(
        '--region',
        default=os.environ.get('AWS_REGION', 'us-east-1'),
        help='AWS region (default: from AWS_REGION env var or us-east-1)',
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
        components = parse_database_url(database_url)
    except ValueError as e:
        print(f'❌ Failed to parse connection string: {e}', file=sys.stderr)
        return 1

    print(f'   Host: {components["host"]}')
    print(f'   Port: {components["port"]}')
    print(f'   Database: {components["database"]}')
    print(f'   Username: {components["username"]}')
    print(f'   SSL mode: {components["sslmode"]}')

    print('🔧 Setting VECTOR_DB_* environment variables...')
    set_vector_db_env(components)

    print('📦 Running alembic upgrade head...')
    result = run_alembic_upgrade(env)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if result.returncode != 0:
        print('❌ Migration failed!', file=sys.stderr)
        return result.returncode

    print('✅ Migration completed successfully')
    print('🔍 Verifying migration with alembic current...')
    verify_result = run_alembic_current(env)
    if verify_result.stdout:
        print(verify_result.stdout)
    if verify_result.stderr:
        print(verify_result.stderr, file=sys.stderr)

    if verify_result.returncode != 0:
        print('⚠️  Verification failed, but migration reported success', file=sys.stderr)
        # Don't fail the workflow on verification failure, but warn

    print('🎉 Migration job completed successfully')
    return 0


if __name__ == '__main__':
    sys.exit(main())
