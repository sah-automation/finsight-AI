# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
"""S3 object storage adapters."""

from __future__ import annotations

from typing import Any

from .aws_s3 import AwsS3
from .boto3_storage import Boto3Storage
from .object_storage import ObjectStorage
from .object_storage_adapter import ObjectStorageAdapter
from .object_store import ObjectStore
from .s3 import S3
from .s3_adapter import S3Adapter
from .s3_bucket import S3Bucket
from .s3_client import S3Client
from .s3_object import S3Object
from .s3_object_storage import S3ObjectStorage
from .s3_object_storage_adapter import S3ObjectStorageAdapter
from .s3_object_store import S3ObjectStore
from .s3_storage import (
    AwsS3ObjectStorage,
    AwsS3Storage,
    S3Storage,
    S3StorageAdapter,
)
from .storage import Storage as StorageAlias
from .storage_adapter import StorageAdapter

# Backwards-friendly alias.
Storage: Any = StorageAlias

__all__ = [
    'S3',
    'AwsS3',
    'AwsS3ObjectStorage',
    'AwsS3Storage',
    'Boto3Storage',
    'ObjectStorage',
    'ObjectStorageAdapter',
    'ObjectStore',
    'S3Adapter',
    'S3Bucket',
    'S3Client',
    'S3Object',
    'S3ObjectStorage',
    'S3ObjectStorageAdapter',
    'S3ObjectStore',
    'S3Storage',
    'S3StorageAdapter',
    'Storage',
    'StorageAdapter',
]
