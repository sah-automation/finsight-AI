"""Adapter-level ObjectStorage implementation (alias to S3 storage)."""

from __future__ import annotations

from .s3_storage import S3Storage as ObjectStorage

__all__ = ['ObjectStorage']
