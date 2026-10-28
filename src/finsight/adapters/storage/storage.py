"""Generic storage adapter alias."""

from __future__ import annotations

from .s3_storage import S3Storage as Storage

__all__ = ['Storage']
