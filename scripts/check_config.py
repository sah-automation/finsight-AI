"""Validate every configuration profile through the typed loader.

`make config-check` runs this script. It loads `config/schema.yaml` merged
with each environment overlay (dev, test, staging, production) through
`finsight.core.config`, so unknown keys, type errors, and invalid combinations
fail here instead of at deploy time.

Values from `.env.example` are used as placeholders only for variables that are
not already set in the current shell. That lets all four profiles be validated
without real secrets. A misspelled variable still fails, because the loader
requires every `${VAR}` reference to resolve.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from finsight.core.config import ConfigError, Environment, load_config

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENV_EXAMPLE = _REPO_ROOT / '.env.example'


def _read_example_values(path: Path) -> dict[str, str]:
    """Parse `KEY=value` lines from the environment template."""
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.split('  #', 1)[0].strip()
    return values


def main() -> int:
    """Load every environment and report the result."""
    placeholders = _read_example_values(_ENV_EXAMPLE)
    injected: list[str] = []
    for key, value in placeholders.items():
        if key not in os.environ:
            os.environ[key] = value
            injected.append(key)

    failures = 0
    for environment in Environment:
        try:
            config = load_config(environment)
        except ConfigError as exc:
            failures += 1
            print(f'FAIL {environment.value}: {exc}', file=sys.stderr)
        else:
            print(f'OK   {environment.value}: environment={config.app.environment.value}')

    for key in injected:
        os.environ.pop(key, None)

    if failures:
        print(f'{failures} configuration profile(s) failed validation', file=sys.stderr)
        return 1
    print(f'Validated {len(Environment)} configuration profiles')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
