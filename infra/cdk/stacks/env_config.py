"""Single reader for ``infra/cdk/config/envs.yaml`` (ADR-0002).

Every stack that needs per-environment settings reads them through here so the
file path, YAML parsing, and fail-loudly error handling live in one place.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ENVS_FILE = Path(__file__).resolve().parent.parent / 'config' / 'envs.yaml'


def load_envs() -> dict[str, Any]:
    """Return every environment's settings keyed by CDK environment name."""
    loaded = yaml.safe_load(ENVS_FILE.read_text(encoding='utf-8')) or {}
    if not isinstance(loaded, dict):
        raise TypeError(f'{ENVS_FILE} must contain a mapping of environment names')
    return loaded


def load_env_config(env_name: str) -> dict[str, Any]:
    """Return one environment's settings, failing loudly on unknown names."""
    loaded = load_envs()
    if env_name not in loaded:
        raise ValueError(f'Unknown environment {env_name!r}; expected one of {sorted(loaded)}')
    config = loaded[env_name]
    if not isinstance(config, dict):
        raise TypeError(f'Environment {env_name!r} must be a mapping')
    return config
