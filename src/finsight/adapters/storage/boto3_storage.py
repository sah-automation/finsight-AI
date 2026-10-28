"""Alias module for S3 object storage adapter."""

from __future__ import annotations

from .s3_storage import S3Storage as Boto3Storage

__all__ = ['Boto3Storage']
