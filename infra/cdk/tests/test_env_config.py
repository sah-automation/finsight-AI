"""Tests for the shared ``config/envs.yaml`` loader.

Every stack reads per-environment settings through ``stacks.env_config``; these
tests lock in the fail-loudly behaviour for unknown or malformed entries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from stacks.env_config import ENVS_FILE, load_alerts_config, load_env_config, load_envs

if TYPE_CHECKING:
    from pathlib import Path


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


def _write_envs(tmp_path: Path, content: str) -> Path:
    envs_file = tmp_path / 'envs.yaml'
    envs_file.write_text(content, encoding='utf-8')
    return envs_file


def test_load_alerts_returns_budget_and_email(tmp_path, monkeypatch) -> None:
    envs_file = _write_envs(
        tmp_path,
        (
            'dev:\n'
            '  alerts:\n'
            '    monthly_budget_usd: 5\n'
            '    notification_email: alerts@example.com\n'
        ),
    )
    monkeypatch.setattr('stacks.env_config.ENVS_FILE', envs_file)

    alerts = load_alerts_config('dev')

    assert alerts == {'monthly_budget_usd': 5, 'notification_email': 'alerts@example.com'}


def test_every_declared_environment_declares_alerts() -> None:
    for env_name, config in load_envs().items():
        alerts = config.get('alerts')
        assert isinstance(alerts, dict), f'environment {env_name!r} is missing an alerts section'


def test_every_declared_environment_has_positive_budget_and_email() -> None:
    for env_name in load_envs():
        alerts = load_alerts_config(env_name)
        assert alerts['monthly_budget_usd'] > 0
        assert '@' in alerts['notification_email']


def test_load_alerts_fails_loudly_on_missing_section(tmp_path, monkeypatch) -> None:
    envs_file = _write_envs(tmp_path, 'dev:\n  name: dev\n')
    monkeypatch.setattr('stacks.env_config.ENVS_FILE', envs_file)

    with pytest.raises(ValueError, match='alerts'):
        load_alerts_config('dev')


def test_load_alerts_fails_loudly_on_non_mapping_section(tmp_path, monkeypatch) -> None:
    envs_file = _write_envs(
        tmp_path,
        'dev:\n  alerts:\n    - monthly_budget_usd: 5\n',
    )
    monkeypatch.setattr('stacks.env_config.ENVS_FILE', envs_file)

    with pytest.raises(TypeError, match='alerts'):
        load_alerts_config('dev')


def test_load_alerts_fails_loudly_on_non_positive_budget(tmp_path, monkeypatch) -> None:
    for bad_budget in ('0', '-3', '"five"', 'true'):
        envs_file = _write_envs(
            tmp_path,
            (
                'dev:\n'
                f'  alerts:\n'
                f'    monthly_budget_usd: {bad_budget}\n'
                '    notification_email: alerts@example.com\n'
            ),
        )
        monkeypatch.setattr('stacks.env_config.ENVS_FILE', envs_file)

        with pytest.raises(ValueError, match='monthly_budget_usd'):
            load_alerts_config('dev')


def test_load_alerts_fails_loudly_on_missing_email(tmp_path, monkeypatch) -> None:
    envs_file = _write_envs(
        tmp_path,
        'dev:\n  alerts:\n    monthly_budget_usd: 5\n',
    )
    monkeypatch.setattr('stacks.env_config.ENVS_FILE', envs_file)

    with pytest.raises(ValueError, match='notification_email'):
        load_alerts_config('dev')
