"""DynamoDB answer cache adapter."""

from __future__ import annotations

from typing import Any

from finsight.domain.ports.answer_cache import AnswerCache as AnswerCachePort

from ._answer_cache_helpers import (
    _LOGGER,
    _TABLES,
    _config_value,
    _first,
    _is_table,
    _resolve_config,
    _text,
)
from ._answer_cache_operations import _AnswerCacheOperations


class AnswerCache(_AnswerCacheOperations, AnswerCachePort):
    """Tenant-scoped answer cache keyed by company and a stamp-aware digest."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: PLR0915
        self.config = _resolve_config(*args, **kwargs)
        config = self.config

        self.table_name = _text(
            _first(
                kwargs,
                'table_name',
                'answer_cache_table',
                'cache_table',
                'dynamo_table',
                'ddb_table',
                'name',
                default=None,
            )
            or _config_value(config, 'table_name', 'answer_cache_table', default='answer-cache')
        ).strip()
        if not self.table_name:
            self.table_name = 'answer-cache'

        self.key_prefix = _text(
            _first(kwargs, 'key_prefix', 'prefix', default=None)
            or _config_value(config, 'key_prefix', default='answer:')
        )

        ttl = _first(kwargs, 'ttl_seconds', 'ttl', default=None)
        if ttl is None:
            ttl = _config_value(config, 'ttl_seconds', 'ttl', default=3600)
        try:
            self.ttl_seconds = int(str(ttl))
        except (TypeError, ValueError):
            self.ttl_seconds = 3600

        max_size = _first(kwargs, 'max_entry_size_bytes', 'max_entry_bytes', default=None)
        if max_size is None:
            max_size = _config_value(config, 'max_entry_size_bytes', default=1024 * 1024)
        try:
            self.max_entry_size_bytes = int(str(max_size))
        except (TypeError, ValueError):
            self.max_entry_size_bytes = 1024 * 1024

        # Switch: answer cache can be disabled. When off, reads miss and writes
        # are skipped, so callers behave as if caching were absent.
        raw_enabled = _first(
            kwargs,
            'answer_cache_enabled',
            'cache_enabled',
            'enabled',
            default=None,
        )
        if raw_enabled is None:
            switches = None
            if config is not None:
                switches = (
                    getattr(config, 'switches', None)
                    if not isinstance(config, dict)
                    else config.get('switches')
                )
            if isinstance(switches, dict):
                raw_enabled = switches.get('answer_cache_enabled')
            elif switches is not None:
                raw_enabled = getattr(switches, 'answer_cache_enabled', None)
        if raw_enabled is None and config is not None and not isinstance(config, dict):
            raw_enabled = getattr(config, 'answer_cache_enabled', None)
        self.enabled = True if raw_enabled is None else bool(raw_enabled)
        self.answer_cache_enabled = self.enabled

        self.table = None
        self.resource = None
        candidate = _first(
            kwargs,
            'table',
            'dynamodb_table',
            'resource',
            'dynamodb',
            'dynamodb_resource',
            'dynamodb_client',
            'client',
            default=None,
        )
        if _is_table(candidate):
            self.table = candidate
        elif candidate is not None:
            if hasattr(candidate, 'Table'):
                try:
                    self.resource = candidate
                    self.table = candidate.Table(self.table_name)
                except Exception as exc:
                    _LOGGER.warning('answer cache table is unavailable: %s', exc)
                    self.table = None
            elif hasattr(candidate, 'resource'):
                try:
                    self.resource = candidate.resource('dynamodb')
                    self.table = self.resource.Table(self.table_name)
                except Exception as exc:
                    _LOGGER.warning('answer cache resource is unavailable: %s', exc)
                    self.table = None

        self._memory = _TABLES.setdefault(self.table_name, {})

    # ------------------------------------------------------------------
    # Key construction
    # ------------------------------------------------------------------


DynamoAnswerCache = AnswerCache
DynamoDBAnswerCache = AnswerCache
DynamoCache = AnswerCache
AnswerCacheAdapter = AnswerCache
DynamoAnswerCacheAdapter = AnswerCache
CacheAdapter = AnswerCache

__all__ = [
    'AnswerCache',
    'AnswerCacheAdapter',
    'CacheAdapter',
    'DynamoAnswerCache',
    'DynamoAnswerCacheAdapter',
    'DynamoCache',
    'DynamoDBAnswerCache',
]
