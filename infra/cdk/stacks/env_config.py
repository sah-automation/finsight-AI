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


def load_alerts_config(env_name: str) -> dict[str, Any]:
    """Return the billing-guardrail alerts settings for one environment.

    Fails loudly when the ``alerts`` section is missing, the monthly budget is
    not a positive number, or the notification email is absent — a silent
    fallback here would drop spend guardrails without anyone noticing.
    """
    config = load_env_config(env_name)
    alerts = config.get('alerts')
    if not isinstance(alerts, dict):
        raise ValueError(
            f'Environment {env_name!r} is missing a valid alerts section; '
            f'expected a mapping with monthly_budget_usd and notification_email'
        )
    budget = alerts.get('monthly_budget_usd')
    if isinstance(budget, bool) or not isinstance(budget, (int, float)) or budget <= 0:
        raise ValueError(
            f'Environment {env_name!r} alerts.monthly_budget_usd must be a '
            f'positive number, got {budget!r}'
        )
    email = alerts.get('notification_email')
    if not isinstance(email, str) or not email.strip() or '@' not in email:
        raise ValueError(
            f'Environment {env_name!r} alerts.notification_email must be a '
            f'non-empty email address, got {email!r}'
        )
    return {'monthly_budget_usd': budget, 'notification_email': email.strip()}
