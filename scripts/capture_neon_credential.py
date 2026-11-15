#!/usr/bin/env python3
"""Capture the Neon connection string into a local, owner-only file.

The value is typed with hidden input and written to a file outside the
repository with owner-only permissions (0600). It is never echoed to the
terminal, never logged, and never committed. A companion script
(``scripts/store_neon_parameter.py``) then hands it to SSM in memory and
destroys the local copy.

Usage:

    uv run python scripts/capture_neon_credential.py
    uv run python scripts/capture_neon_credential.py --file /tmp/other.env
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ENV_FILE = Path.home() / '.config' / 'finsight' / 'neon.env'
KEY = 'NEON_DATABASE_URL'
PREFIX = 'postgresql://'


def write_credential_file(value: str, env_file: Path) -> Path:
    """Write the connection string to ``env_file`` with owner-only permissions.

    Raises ``ValueError`` when the value is not a PostgreSQL connection string —
    a wrong paste must fail here rather than become a broken SSM parameter.
    """
    if not value.startswith(PREFIX):
        raise ValueError(f'the value does not start with {PREFIX} — check the copy')
    env_file.parent.mkdir(parents=True, exist_ok=True)
    escaped = value.replace("'", "'\\''")
    env_file.write_text(f"{KEY}='{escaped}'\n", encoding='utf-8')
    env_file.chmod(0o600)
    return env_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--file',
        type=Path,
        default=ENV_FILE,
        help=f'where to store the credential (default: {ENV_FILE})',
    )
    args = parser.parse_args(argv)

    print('Paste the Neon connection string (hidden input, nothing is echoed).')
    value = getpass.getpass(f'{KEY}: ').strip()
    if not value:
        print('Nothing entered — nothing was written.', file=sys.stderr)
        return 1

    env_file = write_credential_file(value, args.file)
    print(f'Stored {KEY} in {env_file} (permissions 0600, outside the repository).')
    print('Next: uv run python scripts/store_neon_parameter.py')
    return 0


if __name__ == '__main__':
    sys.exit(main())
