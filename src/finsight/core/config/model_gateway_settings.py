"""Model-gateway transport settings resolved from the process environment.

Adapters, entrypoints, and composition must not read ``os.environ`` directly.
This module is part of the single configuration layer and exposes the model
gateway settings (issue #330) as plain values:

- ``model_gateway_settings`` — caller-side settings the API function needs to
  reach the gateway (base URL, optional bearer token, signing region).
- ``gateway_runtime_settings`` — settings the gateway function itself needs
  (optional master key for the bearer check; IAM function-URL auth is the
  enforced control, the key is defense in depth when configured).
"""

from __future__ import annotations

import os


def model_gateway_settings() -> dict[str, str]:
    """Return caller-side gateway transport settings sourced from the environment.

    Only values that are actually present are returned so callers can fail
    loudly on a missing base URL while treating the bearer token and region as
    optional refinements.
    """
    base_url = os.environ.get('MODEL_GATEWAY_URL')
    if not base_url:
        return {}

    settings: dict[str, str] = {'base_url': base_url}

    auth_token = os.environ.get('MODEL_GATEWAY_AUTH_TOKEN')
    if auth_token:
        settings['auth_token'] = auth_token

    region = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION')
    if region:
        settings['region'] = region

    return settings


def gateway_runtime_settings() -> dict[str, str]:
    """Return gateway-side runtime settings sourced from the environment."""
    master_key = os.environ.get('MODEL_GATEWAY_MASTER_KEY')
    if not master_key:
        return {}

    return {'master_key': master_key}


__all__ = ['gateway_runtime_settings', 'model_gateway_settings']
