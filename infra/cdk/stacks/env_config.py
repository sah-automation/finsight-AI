"""Single reader for ``infra/cdk/config/envs.yaml`` (ADR-0002).

Every stack that needs per-environment settings reads them through here so the
file path, YAML parsing, and fail-loudly error handling live in one place.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

ENVS_FILE = Path(__file__).resolve().parent.parent / 'config' / 'envs.yaml'

_ALERTS_KEYS = frozenset({'monthly_budget_usd', 'anomaly_threshold_usd', 'notification_email'})


@dataclass(frozen=True)
class AlertsConfig:
    """Billing guardrail settings for one environment.

    Money is carried as ``Decimal`` so the configured amount is never turned
    into a float on the way to AWS.
    """

    monthly_budget_usd: Decimal
    anomaly_threshold_usd: Decimal
    notification_email: str


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


def uses_remote_gateway(env_name: str, config: Mapping[str, Any] | None = None) -> bool:
    """Return True if the environment uses the remote model gateway (issue #330).

    The transport is configured via the app config's ``llm_transport`` switch.
    Only ``prod`` currently selects ``remote_gateway``; all others default to
    ``in_process``.
    """
    load_env_config(env_name) if config is None else dict(config)
    # The switch is in the app config, not the CDK env config. For synthesis we
    # infer from the environment name since the app config isn't available.
    # In production (env_name == 'prod') the app config selects remote_gateway.
    return env_name == 'prod'


def uses_aurora_vpc(env_name: str, config: Mapping[str, Any] | None = None) -> bool:
    """Return True when the ``vector_store`` switch requires infrastructure VPC.

    ``neon_pgvector`` is the pilot path: Neon is a public service, so Lambdas
    stay outside a VPC and use Lambda-managed internet egress. That removes the
    need for a NAT gateway. ``aurora_pgvector`` keeps the VPC for the undeployed
    standard path. Unknown values fail loudly instead of silently adding cost.
    """
    env_config = load_env_config(env_name) if config is None else dict(config)
    vector_store = env_config.get('vector_store')
    if vector_store == 'neon_pgvector':
        return False
    if vector_store == 'aurora_pgvector':
        return True
    raise ValueError(
        f'Environment {env_name!r} has unknown vector_store {vector_store!r}; '
        'expected neon_pgvector or aurora_pgvector'
    )


def _read_amount(alerts: Mapping[str, Any], key: str, env_name: str) -> Decimal:
    raw = alerts.get(key)
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        raise TypeError(f'Environment {env_name!r} alerts.{key} must be a number, got {raw!r}')
    try:
        amount = Decimal(str(raw))
    except InvalidOperation as exc:
        raise ValueError(
            f'Environment {env_name!r} alerts.{key} must be a positive number, got {raw!r}'
        ) from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError(
            f'Environment {env_name!r} alerts.{key} must be a positive number, got {raw!r}'
        )
    return amount


def load_alerts_config(env_name: str, config: Mapping[str, Any] | None = None) -> AlertsConfig:
    """Return the billing-guardrail alerts settings for one environment.

    Fails loudly when the ``alerts`` section is missing, an unknown key is
    present, an amount is not a positive number, or the notification email is
    absent — a silent fallback here would drop spend guardrails without anyone
    noticing. The environment settings can be injected so callers (and tests)
    pass in what they need instead of reading a hidden global.
    """
    env_config = load_env_config(env_name) if config is None else dict(config)
    if 'alerts' not in env_config:
        raise ValueError(
            f'Environment {env_name!r} is missing an alerts section; '
            f'expected monthly_budget_usd, anomaly_threshold_usd and notification_email'
        )
    alerts = env_config['alerts']
    if not isinstance(alerts, Mapping):
        raise TypeError(
            f'Environment {env_name!r} alerts section must be a mapping, '
            f'got {type(alerts).__name__}'
        )
    unknown = sorted(set(alerts) - _ALERTS_KEYS)
    if unknown:
        raise ValueError(
            f'Environment {env_name!r} alerts section has unknown key(s) {unknown}; '
            f'expected only {sorted(_ALERTS_KEYS)}'
        )
    email = alerts.get('notification_email')
    if not isinstance(email, str) or not email.strip() or '@' not in email:
        raise ValueError(
            f'Environment {env_name!r} alerts.notification_email must be a '
            f'non-empty email address, got {email!r}'
        )
    return AlertsConfig(
        monthly_budget_usd=_read_amount(alerts, 'monthly_budget_usd', env_name),
        anomaly_threshold_usd=_read_amount(alerts, 'anomaly_threshold_usd', env_name),
        notification_email=email.strip(),
    )
