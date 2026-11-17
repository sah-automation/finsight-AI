#!/usr/bin/env python3
"""Inject secret-backed runtime environment variables into the API Lambda.

CDK must not own secret values: the Neon database URL and the model-gateway
master key are SecureStrings in SSM and never flow through CDK synthesis,
GitHub secrets, or workflow logs. Because ``update-function-configuration``
during a CDK deploy resets the function's environment to the CDK-owned set,
this script re-injects the secret-backed variables after every deploy:

1. ``/finsight/{env}/neon/database_url`` → ``VECTOR_DB_*`` (the same parsing
   the migration script uses, matching the config loader's expectations).
2. ``/finsight/{env}/model_gateway_master_key`` → ``MODEL_GATEWAY_AUTH_TOKEN``
   (the bearer defense-in-depth token for the remote model gateway).

Existing environment variables (CDK-managed buckets, tables, queues, Cognito
ids) are preserved — only the secret-backed keys are added or overwritten.

Usage:
    uv run python scripts/sync_lambda_env.py --environment prod --region us-east-1
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

import boto3  # type: ignore[import-untyped]

# ``scripts/`` is not a package: running this file puts it on sys.path[0],
# but importing it via importlib (as the tests do) needs the explicit entry.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# Reuse the shared Neon URL parser so both deploy entrypoints (migration and
# env sync) decompose the SSM-stored connection string identically.
from neon_connection import (  # noqa: E402
    build_vector_db_env,
    parse_database_url,
)

NEON_PARAMETER_PATTERN = '/finsight/{env}/neon/database_url'
MASTER_KEY_PARAMETER_PATTERN = '/finsight/{env}/model_gateway_master_key'

# CDK creates the parameter with this scaffold value for fresh environments;
# the real key is a one-time SSM rotation after the first deploy.
PLACEHOLDER_MASTER_KEY = 'PLACEHOLDER_REPLACE_AT_DEPLOY'

ParameterFetcher = Callable[[str, str], str]


def vector_db_vars(database_url: str) -> dict[str, str]:
    """Build the VECTOR_DB_* variables from the Neon connection string."""
    return build_vector_db_env(parse_database_url(database_url))


def default_function_name(env: str) -> str:
    """Mirror the compute stack's API function naming."""
    return f'finsight-{env}-api'


def fetch_parameter(parameter_name: str, region: str) -> str:
    """Retrieve a SecureString parameter from SSM Parameter Store."""
    client = boto3.client('ssm', region_name=region)
    response = client.get_parameter(Name=parameter_name, WithDecryption=True)
    return response['Parameter']['Value']  # type: ignore[no-any-return]


def lambda_env_vars(fetch: ParameterFetcher, env: str, region: str) -> dict[str, str]:
    """Resolve every secret-backed variable the API Lambda needs.

    Raises if any backing parameter is missing — a partial injection would
    leave the function broken in a way that is hard to diagnose later.
    """
    database_url = fetch(NEON_PARAMETER_PATTERN.format(env=env), region)
    master_key = fetch(MASTER_KEY_PARAMETER_PATTERN.format(env=env), region)
    if master_key == PLACEHOLDER_MASTER_KEY:
        raise RuntimeError(
            f'SSM parameter {MASTER_KEY_PARAMETER_PATTERN.format(env=env)} still holds '
            f'the CDK scaffold placeholder. Set the real master key first: '
            f'aws ssm put-parameter --name {MASTER_KEY_PARAMETER_PATTERN.format(env=env)} '
            f'--type SecureString --value <generated-key> --overwrite'
        )

    env_vars = vector_db_vars(database_url)
    env_vars['MODEL_GATEWAY_AUTH_TOKEN'] = master_key
    return env_vars


def merge_lambda_env(existing: dict[str, str], synced: dict[str, str]) -> dict[str, str]:
    """Merge secret-backed variables into the function's current environment.

    CDK-managed variables are preserved; synced variables win on conflict
    (they carry the live SSM values).
    """
    merged = dict(existing)
    merged.update(synced)
    return merged


def sync_lambda_env(function_name: str, env_vars: dict[str, str], region: str) -> None:
    """Apply the merged environment to the deployed Lambda function."""
    client = boto3.client('lambda', region_name=region)
    config = client.get_function_configuration(FunctionName=function_name)
    existing = config.get('Environment', {}).get('Variables', {}) or {}

    merged = merge_lambda_env(existing, env_vars)

    client.update_function_configuration(
        FunctionName=function_name,
        Environment={'Variables': merged},
    )
    print(
        f'✓ Synced {len(env_vars)} secret-backed environment variables into '
        f'{function_name} ({len(merged)} total; secrets never logged)'
    )


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and sync the deployed function's environment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--environment',
        required=True,
        help='CDK environment name (e.g. prod)',
    )
    parser.add_argument(
        '--region',
        required=True,
        help='AWS region (from AWS_REGION env var)',
    )
    parser.add_argument(
        '--function-name',
        help=f'Override the target function (default: {default_function_name("{env}")})',
    )
    args = parser.parse_args(argv)

    function_name = args.function_name or default_function_name(args.environment)

    print(f'🔐 Resolving secret-backed variables for {args.environment} from SSM')
    env_vars = lambda_env_vars(fetch=fetch_parameter, env=args.environment, region=args.region)
    sync_lambda_env(function_name, env_vars, args.region)
    print(f'✓ Environment sync complete for {function_name} in {args.region}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
