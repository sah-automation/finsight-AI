"""DynamoDB answer cache adapter.

The cache key is always built by :func:`finsight.domain.services.cache_key.build_answer_cache_key`,
so company, role, access scope, question and the document stamp are part of
every key. A changed document stamp therefore makes older answers
unaddressable, and a lifecycle change clears the company's cached answers.

The adapter only talks to a DynamoDB table/resource/client that was injected by
the composition root. Without one it keeps entries in a process-local store so
contract tests never reach the network.
"""

from __future__ import annotations

import inspect
import json
import logging
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from finsight.domain.ports.answer_cache import AnswerCache as AnswerCachePort
from finsight.domain.services.cache_key import build_answer_cache_key

_LOGGER = logging.getLogger(__name__)

_TABLES: dict[str, dict[str, dict[str, Any]]] = {}

_LIFECYCLE_CLEAR_EVENTS = frozenset(
    {
        'document.updated',
        'document.deleted',
        'document.restored',
        'document.purged',
        'document.reprocessed',
    }
)


class _CacheContext:
    """Minimal answer context consumed by ``build_answer_cache_key``."""

    def __init__(self, company_id: object, role: object, access_scope: object) -> None:
        self.company_id = company_id
        self.role = role
        self.access_scope = _as_sequence(access_scope)


def _as_sequence(value: object) -> list[object]:
    """Return an iterable as a list, treating text as a single value-free scope."""
    if value is None or isinstance(value, (str, bytes)):
        return []
    if isinstance(value, Iterable):
        return list(value)
    return []


def _text(value: object) -> str:
    return '' if value is None else str(value)


def _stamp_value(document_stamp: object) -> str:
    return _text(getattr(document_stamp, 'value', document_stamp))


def _resolve_config(*args: Any, **kwargs: Any) -> Any:
    for arg in args:
        if arg is None:
            continue
        if hasattr(arg, 'caches') or hasattr(arg, 'switches') or hasattr(arg, 'app'):
            return arg
    for key in ('config', 'settings', 'configuration', 'app_config', 'ctx', 'context'):
        value = kwargs.get(key)
        if value is not None:
            return value
    for key in ('container', 'composition', 'root', 'app'):
        container = kwargs.get(key)
        if container is not None:
            config = getattr(container, 'config', None)
            if config is not None:
                return config
    return None


def _config_value(config: Any, *names: str, default: Any = None) -> Any:
    sections = ('caches', 'cache', 'answer_cache', 'dynamodb')
    for name in names:
        if config is None:
            break
        if isinstance(config, dict):
            if config.get(name) is not None:
                return config.get(name)
            for section in sections:
                sec = config.get(section)
                if isinstance(sec, dict) and sec.get(name) is not None:
                    return sec.get(name)
        else:
            value = getattr(config, name, None)
            if value is not None:
                return value
            for section in sections:
                sec = getattr(config, section, None)
                if sec is None:
                    continue
                value = sec.get(name) if isinstance(sec, dict) else getattr(sec, name, None)
                if value is not None:
                    return value
    return default


def _first(kwargs: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if kwargs.get(name) is not None:
            return kwargs.get(name)
    return default


def _is_table(obj: Any) -> bool:
    return obj is not None and any(
        hasattr(obj, method) for method in ('put_item', 'get_item', 'delete_item', 'query', 'scan')
    )


async def _maybe_await(value: Any, *args: Any, **kwargs: Any) -> Any:
    result = value(*args, **kwargs) if callable(value) else value
    if inspect.isawaitable(result):
        return await result
    return result


def _encode_value(value: object) -> tuple[str, str]:
    if value is None or isinstance(value, (str, int, float, bool)):
        return json.dumps(value), 'json'
    try:
        return json.dumps(value, sort_keys=True, default=str), 'json'
    except (TypeError, ValueError):
        return repr(value), 'repr'


def _decode_value(payload: object, encoding: object) -> object:
    if payload is None:
        return None
    if encoding == 'repr':
        return payload
    if not isinstance(payload, str):
        return payload
    try:
        return json.loads(payload)
    except (TypeError, ValueError):
        return payload


class AnswerCache(AnswerCachePort):
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

    def _build_key(
        self,
        company_id: object,
        *,
        key: str | None = None,
        role: object = None,
        access_scope: object = None,
        question: str | None = None,
        document_stamp: object = None,
        **kwargs: object,
    ) -> str:
        if key is not None and str(key).strip():
            explicit = str(key).strip()
            if explicit.startswith(self.key_prefix):
                return explicit
            return f'{self.key_prefix}{explicit}'
        context = _CacheContext(company_id, role, access_scope)
        digest = build_answer_cache_key(
            context,
            question or '',
            _stamp_value(document_stamp),
        )
        return f'{self.key_prefix}{digest}'

    def build_key(
        self,
        company_id: object,
        *,
        key: str | None = None,
        role: object = None,
        access_scope: object = None,
        question: str | None = None,
        document_stamp: object = None,
        **kwargs: object,
    ) -> str:
        """Return the cache key that would be used for this lookup."""
        return self._build_key(
            company_id,
            key=key,
            role=role,
            access_scope=access_scope,
            question=question,
            document_stamp=document_stamp,
            **kwargs,
        )

    key_for = build_key

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------

    async def get(
        self,
        company_id: object,
        *,
        key: str | None = None,
        role: object = None,
        access_scope: object = None,
        question: str | None = None,
        document_stamp: object = None,
        **kwargs: object,
    ) -> object:
        if not self.enabled:
            return None
        cache_key = self._build_key(
            company_id,
            key=key,
            role=role,
            access_scope=access_scope,
            question=question,
            document_stamp=document_stamp,
            **kwargs,
        )
        item = await self._fetch(_text(company_id), cache_key)
        if item is None or self._expired(item):
            return None
        return _decode_value(item.get('value'), item.get('encoding'))

    async def set(
        self,
        company_id: object,
        value: object,
        *,
        key: str | None = None,
        ttl_seconds: int | None = None,
        role: object = None,
        access_scope: object = None,
        question: str | None = None,
        document_stamp: object = None,
        **kwargs: object,
    ) -> None:
        if not self.enabled:
            return
        cache_key = self._build_key(
            company_id,
            key=key,
            role=role,
            access_scope=access_scope,
            question=question,
            document_stamp=document_stamp,
            **kwargs,
        )
        payload, encoding = _encode_value(value)
        if (
            self.max_entry_size_bytes > 0
            and len(payload.encode('utf-8')) > self.max_entry_size_bytes
        ):
            raise ValueError(
                f'answer cache entry is {len(payload.encode("utf-8"))} bytes, '
                f'limit is {self.max_entry_size_bytes}'
            )
        ttl = self.ttl_seconds if ttl_seconds is None else int(ttl_seconds)
        now = datetime.now(UTC)
        item: dict[str, Any] = {
            'pk': _text(company_id),
            'sk': cache_key,
            'company_id': _text(company_id),
            'cache_key': cache_key,
            'value': payload,
            'encoding': encoding,
            'created_at': now.isoformat(),
            'updated_at': now.isoformat(),
            'document_stamp': _stamp_value(document_stamp),
            'role': _text(getattr(role, 'value', role)),
            'access_scope': [
                _text(getattr(entry, 'value', entry)) for entry in _as_sequence(access_scope)
            ],
            'question': question or '',
        }
        if ttl > 0:
            item['ttl'] = int(now.timestamp()) + ttl
        await self._persist(item)

    async def clear(self, company_id: object, **kwargs: object) -> None:
        company = _text(company_id)
        self._memory.pop(company, None)
        if self.table is None:
            return
        await self._delete_remote_company(company)

    async def delete(
        self,
        company_id: object,
        key: str | None = None,
        **kwargs: Any,
    ) -> bool:
        if key is None:
            await self.clear(company_id, **kwargs)
            return True
        cache_key = self._build_key(company_id, key=key, **kwargs)
        company = _text(company_id)
        store = self._memory.setdefault(company, {})
        existed = store.pop(cache_key, None) is not None
        if self.table is not None:
            try:
                await _maybe_await(
                    self.table.delete_item,
                    Key={'pk': company, 'sk': cache_key},
                )
                existed = True
            except Exception as exc:
                _LOGGER.debug('answer cache delete failed: %s', exc)
        return existed

    # ------------------------------------------------------------------
    # Lifecycle invalidation
    # ------------------------------------------------------------------

    async def clear_on_upload(self, company_id: object, **kwargs: object) -> None:
        await self.clear(company_id, **kwargs)

    async def clear_on_update(self, company_id: object, **kwargs: object) -> None:
        await self.clear(company_id, **kwargs)

    async def clear_on_delete(self, company_id: object, **kwargs: object) -> None:
        await self.clear(company_id, **kwargs)

    async def clear_on_reprocess(self, company_id: object, **kwargs: object) -> None:
        await self.clear(company_id, **kwargs)

    async def handle_change_event(
        self,
        company_id: object,
        event: object,
        **kwargs: object,
    ) -> bool:
        """Clear cached answers when a document lifecycle event is published."""
        event_company = _text(getattr(event, 'company_id', company_id))
        if event_company and event_company != _text(company_id):
            raise ValueError('change event company_id must match the cache tenant')
        event_type = _text(getattr(event, 'event_type', '')).strip().lower()
        if event_type in _LIFECYCLE_CLEAR_EVENTS:
            await self.clear(company_id, **kwargs)
            return True
        return False

    on_change_event = handle_change_event
    clear_for_event = handle_change_event

    # ------------------------------------------------------------------
    # Storage helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _expired(item: dict[str, Any]) -> bool:
        ttl = item.get('ttl')
        try:
            return ttl is not None and int(str(ttl)) <= int(time.time())
        except (TypeError, ValueError):
            return False

    async def _fetch(self, company_id: str, cache_key: str) -> dict[str, Any] | None:
        item = self._memory.get(company_id, {}).get(cache_key)
        if isinstance(item, dict):
            return dict(item)
        if self.table is None:
            return None
        try:
            response = await _maybe_await(
                self.table.get_item,
                Key={'pk': company_id, 'sk': cache_key},
                ConsistentRead=True,
            )
        except Exception as exc:
            _LOGGER.debug('answer cache read failed: %s', exc)
            return None
        remote = response.get('Item') if isinstance(response, dict) else None
        if not isinstance(remote, dict):
            return None
        if _text(remote.get('company_id')) not in ('', company_id):
            return None
        self._memory.setdefault(company_id, {})[cache_key] = dict(remote)
        return dict(remote)

    async def _persist(self, item: dict[str, Any]) -> None:
        company = _text(item.get('company_id'))
        cache_key = _text(item.get('sk'))
        self._memory.setdefault(company, {})[cache_key] = dict(item)
        if self.table is None:
            return
        try:
            await _maybe_await(self.table.put_item, Item=item)
        except Exception as exc:
            _LOGGER.warning('answer cache write failed: %s', exc)

    async def _delete_remote_company(self, company_id: str) -> None:
        if self.table is None:
            return
        keys: list[dict[str, str]] = []
        try:
            response = await _maybe_await(
                self.table.query,
                KeyConditionExpression='pk = :pk',
                ExpressionAttributeValues={':pk': company_id},
            )
            if isinstance(response, dict):
                keys.extend(
                    {'pk': company_id, 'sk': _text(row.get('sk'))}
                    for row in response.get('Items', [])
                    if isinstance(row, dict)
                )
        except Exception as exc:
            _LOGGER.debug('answer cache query failed: %s', exc)
        if not keys:
            try:
                response = await _maybe_await(
                    self.table.scan,
                    FilterExpression='pk = :pk',
                    ExpressionAttributeValues={':pk': company_id},
                )
                if isinstance(response, dict):
                    keys.extend(
                        {'pk': company_id, 'sk': _text(row.get('sk'))}
                        for row in response.get('Items', [])
                        if isinstance(row, dict)
                    )
            except Exception as exc:
                _LOGGER.debug('answer cache scan failed: %s', exc)
        for key in keys:
            try:
                await _maybe_await(self.table.delete_item, Key=key)
            except Exception as exc:
                _LOGGER.warning('answer cache cleanup failed: %s', exc)


# Naming variants used across the project/tests.
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
