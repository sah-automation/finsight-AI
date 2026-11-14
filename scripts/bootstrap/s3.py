"""S3 upload module for test bootstrap.

Builds the boto3 client through the :func:`aws_client_settings` config seam
(the same seam the adapters use) instead of hard-coding LocalStack values.
LocalStack default credentials are only used when the resolved endpoint is a
local one, mirroring ``adapters/queue/_sqs_queue_aws_config.py``.
"""

from __future__ import annotations

import logging
import socket
from typing import Any
from urllib.parse import urlparse

import boto3

from finsight.core.config import aws_client_settings

logger = logging.getLogger('bootstrap_test_data.s3')

_LOCAL_ENDPOINT_HOSTS = {'localhost', '127.0.0.1', '::1'}

_CONTENT_TYPES = {
    'pdf': 'application/pdf',
    'scan': 'application/pdf',
    'image': 'image/png',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'csv': 'text/csv',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}


def guess_content_type(file_type: str) -> str:
    """Guess MIME content type from file type."""
    return _CONTENT_TYPES.get(file_type, 'application/octet-stream')


def _is_local_endpoint(endpoint_url: Any) -> bool:
    if not endpoint_url:
        return False
    parsed = urlparse(str(endpoint_url))
    host = (parsed.hostname or '').lower()
    return host in _LOCAL_ENDPOINT_HOSTS or host.endswith('.localstack.cloud')


def _localstack_reachable(endpoint_url: str) -> bool:
    """Return True if LocalStack S3 endpoint (port 4566) answers TCP."""
    try:
        parsed = urlparse(endpoint_url)
        host = parsed.hostname or 'localhost'
        port = parsed.port or 4566
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:  # pragma: no cover - exercised only without LocalStack
        return False


def _build_s3_client(config: Any) -> Any:
    """Build a boto3 S3 client from the config seam and storage settings."""
    storage_config = config.storage
    settings = aws_client_settings()

    endpoint_url = settings.get('endpoint_url')
    region_name = settings.get('region_name') or getattr(storage_config, 'region', None)

    kwargs: dict[str, Any] = {}
    if region_name:
        kwargs['region_name'] = str(region_name)
    if endpoint_url:
        kwargs['endpoint_url'] = str(endpoint_url)

    access_key_id = settings.get('aws_access_key_id')
    secret_access_key = settings.get('aws_secret_access_key')
    if _is_local_endpoint(endpoint_url) and (not access_key_id or not secret_access_key):
        logger.debug('Local endpoint %s: using LocalStack default credentials', endpoint_url)
        access_key_id = access_key_id or 'test'
        secret_access_key = secret_access_key or 'test'
    if access_key_id:
        kwargs['aws_access_key_id'] = access_key_id
    if secret_access_key:
        kwargs['aws_secret_access_key'] = secret_access_key

    return boto3.client('s3', **kwargs)


async def upload_fixtures_to_s3(config: Any, records: list[dict[str, Any]]) -> None:
    """Upload fixture files to S3.

    When LocalStack is not reachable (e.g. Migrations job runs Postgres only),
    this function logs a warning and returns without error so the bootstrap
    can complete for the database steps.
    """
    settings = aws_client_settings()
    endpoint_url = settings.get('endpoint_url')
    if _is_local_endpoint(endpoint_url) and not _localstack_reachable(str(endpoint_url)):
        logger.warning(
            'LocalStack S3 endpoint %s not reachable; skipping S3 fixture uploads',
            endpoint_url,
        )
        return

    bucket = config.storage.documents_bucket
    s3_client = _build_s3_client(config)

    # Ensure bucket exists
    try:
        s3_client.head_bucket(Bucket=bucket)
    except boto3.exceptions.Boto3Error:
        s3_client.create_bucket(Bucket=bucket)
        logger.info('Created bucket: %s', bucket)

    for record in records:
        fixture = record['fixture']
        filepath = record['filepath']
        s3_key = record['s3_key']
        file_hash = record['file_hash']

        # Check if object already exists with same hash (idempotent upload).
        # ETag is an MD5 digest, so compare the file-hash metadata instead.
        try:
            head = s3_client.head_object(Bucket=bucket, Key=s3_key)
            existing_hash = (head.get('Metadata') or {}).get('file-hash', '')
            if existing_hash == file_hash:
                logger.info('  Object already exists with same hash, skipping: %s', s3_key)
                continue
            logger.info('  Object exists with different hash, overwriting: %s', s3_key)
        except s3_client.exceptions.ClientError as e:
            if e.response['Error']['Code'] != '404':
                raise
            # Object doesn't exist, will upload

        # Upload file to S3
        with filepath.open('rb') as f:
            s3_client.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=f,
                ContentType=guess_content_type(fixture['file_type']),
                Metadata={
                    'file-hash': file_hash,
                    'company-id': str(record['company_id']),
                    'document-id': str(record['document_id']),
                    'version-id': str(record['version_id']),
                },
            )
        logger.info('  Uploaded successfully: %s', s3_key)
