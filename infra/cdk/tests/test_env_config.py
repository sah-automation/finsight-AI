"""Tests for the shared ``config/envs.yaml`` loader.

Every stack reads per-environment settings through ``stacks.env_config``; these
tests lock in the fail-loudly behaviour for unknown or malformed entries.
"""

from __future__ import annotations

import pytest
from stacks.env_config import ENVS_FILE, load_env_config, load_envs


def test_load_envs_covers_every_declared_environment() -> None:
    envs = load_envs()

    assert set(envs) == {'dev', 'staging', 'prod'}


def test_load_env_config_returns_that_environment() -> None:
    config = load_env_config('prod')

    assert config['name'] == 'prod'
    assert config['environment'] == 'production'


def test_load_env_config_rejects_unknown_environment() -> None:
    with pytest.raises(ValueError, match='Unknown environment'):
        load_env_config('nope')


def test_envs_file_points_at_the_cdk_config() -> None:
    assert ENVS_FILE.name == 'envs.yaml'
    assert ENVS_FILE.parent.name == 'config'
    assert ENVS_FILE.is_file()
