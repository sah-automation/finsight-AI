"""S3 object storage adapters."""

from __future__ import annotations

from .s3_storage import *  # noqa: F403

ObjectStorage = S3Storage

# Compatibility spellings for the same adapter.
AwsS3 = S3Storage
Boto3Storage = S3Storage
ObjectStore = S3Storage
S3Adapter = S3Storage
S3Bucket = S3Storage
S3Client = S3Storage
S3Object = S3Storage
S3ObjectStore = S3Storage
StorageAdapter = S3Storage


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
