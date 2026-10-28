"""Alias module for object storage adapter."""

from __future__ import annotations

from .s3_storage import S3Storage as ObjectStorageAdapter

__all__ = ['ObjectStorageAdapter']
