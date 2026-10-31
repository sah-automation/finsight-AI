# ruff: noqa: ANN401, BLE001, F403, F405, I001, PLR0911, PLR0912, PLR0913, N806, S110
from __future__ import annotations

import inspect
import json
import logging
from collections.abc import Iterable
from typing import Any

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


__all__ = [
    '_LIFECYCLE_CLEAR_EVENTS',
    '_LOGGER',
    '_TABLES',
    '_CacheContext',
    '_as_sequence',
    '_config_value',
    '_decode_value',
    '_encode_value',
    '_first',
    '_is_table',
    '_maybe_await',
    '_resolve_config',
    '_stamp_value',
    '_text',
]


async def _delete_remote_company(self: Any, company_id: str) -> None:
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
