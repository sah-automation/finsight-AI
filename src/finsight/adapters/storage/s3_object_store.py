"""Alias module for S3 object storage adapter."""

from __future__ import annotations

from .s3_storage import S3Storage as S3ObjectStore

__all__ = ['S3ObjectStore']
