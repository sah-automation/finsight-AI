"""Resolve AWS client settings for the SQS adapter without reading env directly."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from finsight.core.config import aws_client_settings

logger = logging.getLogger(__name__)

_PLACEHOLDER_QUEUE_HOST = 'sqs.test'
_LOCAL_ENDPOINT_HOSTS = {
    'localhost',
    '127.0.0.1',
    '::1',
    'localstack',
}


def _queue_endpoint_url(queue: Any) -> str | None:
    """Return the service endpoint implied by the configured queue URLs."""
    configured = getattr(queue, 'endpoint_url', None)
    if configured:
        return str(configured)

    queue_config = getattr(queue, 'queue_config', None)
    if queue_config is not None:
        candidate = (
            queue_config.get('endpoint_url')
            if isinstance(queue_config, dict)
            else getattr(queue_config, 'endpoint_url', None)
        )
        if candidate:
            return str(candidate)

    for queue_url in (
        getattr(queue, 'ingestion_queue_url', None),
        getattr(queue, 'reprocessing_queue_url', None),
        getattr(queue, 'reports_queue_url', None),
        getattr(queue, 'dead_letter_queue_url', None),
    ):
        if not queue_url:
            continue
        parsed = urlparse(str(queue_url))
        if parsed.hostname == _PLACEHOLDER_QUEUE_HOST:
            continue
        if parsed.scheme in {'http', 'https'} and parsed.netloc:
            return f'{parsed.scheme}://{parsed.netloc}'
    return None


def _is_local_endpoint(endpoint_url: Any) -> bool:
    if not endpoint_url:
        return False
    parsed = urlparse(str(endpoint_url))
    host = (parsed.hostname or '').lower()
    return host in _LOCAL_ENDPOINT_HOSTS or host.endswith('.localstack.cloud')


def _aws_client_kwargs(queue: Any) -> dict[str, Any]:
    """Build boto3 client kwargs for the configured AWS/LocalStack environment."""
    settings = aws_client_settings()
    endpoint_url = _queue_endpoint_url(queue)
    if endpoint_url is None:
        endpoint_url = settings.get('endpoint_url')
        if endpoint_url:
            logger.warning(
                'No endpoint found on queue URLs; using AWS_ENDPOINT_URL=%s', endpoint_url
            )

    region_name = getattr(queue, 'region', None) or settings.get('region_name')
    if getattr(queue, 'region', None) is None:
        logger.warning('No queue region configured; using AWS region %s', region_name)

    kwargs: dict[str, Any] = {}
    if region_name:
        kwargs['region_name'] = str(region_name)
    if endpoint_url:
        kwargs['endpoint_url'] = str(endpoint_url)

    access_key_id = settings.get('aws_access_key_id')
    secret_access_key = settings.get('aws_secret_access_key')
    if _is_local_endpoint(endpoint_url):
        if not access_key_id or not secret_access_key:
            logger.warning(
                'Local AWS endpoint %s has no explicit credentials; using LocalStack defaults',
                endpoint_url,
            )
        access_key_id = access_key_id or 'test'
        secret_access_key = secret_access_key or 'test'
    if access_key_id:
        kwargs['aws_access_key_id'] = access_key_id
    if secret_access_key:
        kwargs['aws_secret_access_key'] = secret_access_key
    return kwargs
