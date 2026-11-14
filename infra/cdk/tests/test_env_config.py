"""Tests for the shared ``config/envs.yaml`` loader.

Every stack reads per-environment settings through ``stacks.env_config``; these
tests lock in the fail-loudly behaviour for unknown or malformed entries.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from stacks.env_config import (
    ENVS_FILE,
    AlertsConfig,
    load_alerts_config,
    load_env_config,
    load_envs,
)


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


def test_load_alerts_returns_a_frozen_typed_config() -> None:
    alerts = load_alerts_config('prod')

    assert isinstance(alerts, AlertsConfig)
    assert alerts.monthly_budget_usd == Decimal('5')
    assert alerts.anomaly_threshold_usd == Decimal('5')
    assert '@' in alerts.notification_email
    with pytest.raises(AttributeError):
        alerts.monthly_budget_usd = Decimal('1')  # type: ignore[misc]


def test_load_alerts_accepts_an_injected_config() -> None:
    alerts = load_alerts_config(
        'dev',
        config={
            'alerts': {
                'monthly_budget_usd': 42,
                'anomaly_threshold_usd': '7.5',
                'notification_email': 'alerts@example.com',
            }
        },
    )

    assert alerts.monthly_budget_usd == Decimal('42')
    assert alerts.anomaly_threshold_usd == Decimal('7.5')


def test_every_declared_environment_declares_alerts() -> None:
    for env_name, config in load_envs().items():
        alerts = config.get('alerts')
        assert isinstance(alerts, dict), f'environment {env_name!r} is missing an alerts section'


def test_every_declared_environment_has_positive_budget_threshold_and_email() -> None:
    for env_name in load_envs():
        alerts = load_alerts_config(env_name)
        assert alerts.monthly_budget_usd > 0
        assert alerts.anomaly_threshold_usd > 0
        assert '@' in alerts.notification_email


def test_load_alerts_fails_loudly_on_missing_section() -> None:
    with pytest.raises(ValueError, match='alerts'):
        load_alerts_config('dev', config={'name': 'dev'})


def test_load_alerts_fails_loudly_on_non_mapping_section() -> None:
    with pytest.raises(TypeError, match='alerts'):
        load_alerts_config('dev', config={'alerts': ['monthly_budget_usd: 5']})


@pytest.mark.parametrize('bad_budget', ['0', '-3', '"five"'])
def test_load_alerts_fails_loudly_on_non_positive_budget(bad_budget: str) -> None:
    with pytest.raises(ValueError, match='monthly_budget_usd'):
        load_alerts_config(
            'dev',
            config={
                'alerts': {
                    'monthly_budget_usd': bad_budget,
                    'anomaly_threshold_usd': 5,
                    'notification_email': 'alerts@example.com',
                }
            },
        )


@pytest.mark.parametrize('bad_budget', [True, [1], {'amount': 1}])
def test_load_alerts_fails_loudly_on_budget_of_the_wrong_type(bad_budget: object) -> None:
    with pytest.raises(TypeError, match='monthly_budget_usd'):
        load_alerts_config(
            'dev',
            config={
                'alerts': {
                    'monthly_budget_usd': bad_budget,
                    'anomaly_threshold_usd': 5,
                    'notification_email': 'alerts@example.com',
                }
            },
        )


@pytest.mark.parametrize('bad_threshold', ['0', '-1', '"ten"'])
def test_load_alerts_fails_loudly_on_non_positive_anomaly_threshold(bad_threshold: str) -> None:
    with pytest.raises(ValueError, match='anomaly_threshold_usd'):
        load_alerts_config(
            'dev',
            config={
                'alerts': {
                    'monthly_budget_usd': 5,
                    'anomaly_threshold_usd': bad_threshold,
                    'notification_email': 'alerts@example.com',
                }
            },
        )


def test_load_alerts_fails_loudly_on_missing_email() -> None:
    with pytest.raises(ValueError, match='notification_email'):
        load_alerts_config(
            'dev',
            config={
                'alerts': {
                    'monthly_budget_usd': 5,
                    'anomaly_threshold_usd': 5,
                }
            },
        )


def test_load_alerts_fails_loudly_on_unknown_key() -> None:
    with pytest.raises(ValueError, match='unknown'):
        load_alerts_config(
            'dev',
            config={
                'alerts': {
                    'monthly_budget_usd': 5,
                    'anomaly_threshold_usd': 5,
                    'notification_email': 'alerts@example.com',
                    'monthly_budget': 99,
                }
            },
        )
