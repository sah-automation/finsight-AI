"""Alias module for S3 object storage adapter.

Retained compatibility shim.

Reason: preserves an alternate import path/name for
the canonical module without duplicating implementation.

Removal condition: after callers and tests migrate to
the canonical module and this path is absent from the
alias inventory."""

from __future__ import annotations

from .s3_storage import (
    S3,
    ObjectStorageAdapter,
    S3ObjectStorage,
    S3ObjectStorageAdapter,
    S3Storage,
    S3StorageAdapter,
    Storage,
)

__all__ = [
    'S3',
    'ObjectStorageAdapter',
    'S3ObjectStorage',
    'S3ObjectStorageAdapter',
    'S3Storage',
    'S3StorageAdapter',
    'Storage',
]
