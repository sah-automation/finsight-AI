"""Alias module for S3 object storage adapter.

Retained compatibility shim.

Reason: preserves an alternate import path/name for
the canonical module without duplicating implementation.

Removal condition: after callers and tests migrate to
the canonical module and this path is absent from the
alias inventory."""

from __future__ import annotations

from .s3_storage import S3Storage as Boto3Storage

__all__ = ['Boto3Storage']
