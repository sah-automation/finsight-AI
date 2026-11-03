"""Composition helpers for the source viewer entrypoint (Slice 6.7)."""

from __future__ import annotations

from typing import Any


def _docs_config(config: Any) -> Any:
    docs_cfg = getattr(config, 'documents', None)
    if docs_cfg is None and isinstance(config, dict):
        docs_cfg = config.get('documents')
    if docs_cfg is None:
        raise ValueError('documents config must be configured')
    return docs_cfg


def _get_field(config: Any, name: str) -> Any:
    value = getattr(config, name, None)
    if value is None and isinstance(config, dict):
        value = config.get(name)
    if value is None:
        raise ValueError(f'documents.{name} must be configured')
    return value


def resolve_source_viewer_settings(config: Any) -> tuple[int, int]:
    """Return the configured retention window and original-link TTL."""
    docs_cfg = _docs_config(config)
    retention_days = int(_get_field(docs_cfg, 'version_retention_days'))
    original_link_ttl = int(_get_field(docs_cfg, 'source_original_link_ttl_seconds'))
    return retention_days, original_link_ttl


__all__ = ['resolve_source_viewer_settings']
