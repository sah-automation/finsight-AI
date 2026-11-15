#!/usr/bin/env python3
"""Store the Neon connection string in SSM Parameter Store.

The value is read from the file the capture script wrote, held in memory only,
and handed straight to the SSM API. It is never printed, never written to a
temporary file, never passed as a command-line argument, and never committed.
Verification reads parameter metadata only — the value is never retrieved — and
the local copy is destroyed once the write succeeds.

Usage:

    uv run python scripts/capture_neon_credential.py
    uv run python scripts/store_neon_parameter.py
    uv run python scripts/store_neon_parameter.py --parameter-name /finsight/dev/neon/database_url
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import boto3

ENV_FILE = Path.home() / '.config' / 'finsight' / 'neon.env'
PARAMETER_NAME = '/finsight/prod/neon/database_url'
KEY = 'NEON_DATABASE_URL'
REGION = os.environ.get('AWS_REGION', 'us-east-1')


def read_value(env_file: Path) -> str:
    """Read the connection string from the owner's credential file."""
    if not env_file.is_file():
        raise SystemExit(
            f'{env_file} does not exist — run scripts/capture_neon_credential.py first'
        )
    for line in env_file.read_text(encoding='utf-8').splitlines():
        if not line.startswith(f'{KEY}='):
            continue
        value = line.split('=', 1)[1].strip()
        if value.startswith("'") and value.endswith("'"):
            value = value[1:-1].replace("'\\''", "'")
        if not value:
            break
        return value
    raise SystemExit(f'{KEY} is not set in {env_file}')


def store_parameter(client: Any, value: str, parameter_name: str) -> None:
    """Write the value to SSM as a SecureString."""
    client.put_parameter(
        Name=parameter_name,
        Value=value,
        Type='SecureString',
        Overwrite=True,
        Description='Neon connection string for FinSight AI.',
    )


def store_and_verify(client: Any, env_file: Path, parameter_name: str) -> dict[str, Any]:
    """Store the credential, verify it by metadata, then destroy the local copy."""
    value = read_value(env_file)
    store_parameter(client, value, parameter_name)
    del value

    described = client.describe_parameters(
        ParameterFilters=[{'Key': 'Name', 'Option': 'Equals', 'Values': [parameter_name]}]
    )['Parameters']
    if not described:
        raise SystemExit(f'{parameter_name} was not found after the write')
    parameter = described[0]

    _destroy(env_file)

    return {
        'name': parameter['Name'],
        'type': parameter['Type'],
        'version': parameter['Version'],
        'last_modified': str(parameter.get('LastModifiedDate', '')),
    }


def _destroy(env_file: Path) -> None:
    """Overwrite the local credential file with zeros, then remove it."""
    if not env_file.exists():
        return
    with env_file.open('wb') as handle:
        size = env_file.stat().st_size
        handle.write(b'\0' * size)
    env_file.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--file',
        type=Path,
        default=ENV_FILE,
        help=f'where the credential is staged (default: {ENV_FILE})',
    )
    parser.add_argument(
        '--parameter-name',
        default=PARAMETER_NAME,
        help=f'the SSM parameter to write (default: {PARAMETER_NAME})',
    )
    parser.add_argument('--region', default=REGION, help='AWS region (default: us-east-1)')
    args = parser.parse_args(argv)

    client = boto3.client('ssm', region_name=args.region)
    report = store_and_verify(client, args.file, args.parameter_name)

    print(f'stored {report["name"]}')
    print(f'  type       : {report["type"]}')
    print(f'  version    : {report["version"]}')
    print(f'  last write : {report["last_modified"]}')
    print('  value      : never read back')
    print(f'removed the local staging file {args.file}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
