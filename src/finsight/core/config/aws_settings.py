"""AWS SDK client settings resolved from the process environment.

Adapters must not read ``os.environ`` directly. This module is part of the
single configuration layer and exposes the standard AWS SDK environment
variables as plain client keyword arguments.
"""

from __future__ import annotations

import os

from finsight.core.config.loader import ConfigError


def aws_client_settings() -> dict[str, str]:
    """Return boto3 client keyword arguments sourced from the environment.

    Only values that are actually present are returned so that boto3 can fall
    back to its normal credential provider chain when no explicit credentials
    are configured.
    """
    region = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION')
    if not region:
        raise ConfigError('AWS_REGION or AWS_DEFAULT_REGION must be set')

    settings: dict[str, str] = {
        'region_name': region,
    }

    endpoint_url = os.environ.get('AWS_ENDPOINT_URL')
    if endpoint_url:
        settings['endpoint_url'] = endpoint_url

    access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
    if access_key_id:
        settings['aws_access_key_id'] = access_key_id

    secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    if secret_access_key:
        settings['aws_secret_access_key'] = secret_access_key

    return settings


__all__ = ['aws_client_settings']
