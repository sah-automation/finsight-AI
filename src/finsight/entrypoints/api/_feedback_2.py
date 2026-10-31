# ruff: noqa: BLE001, PLR0912, S110, S112, B004, B025, I001, F403, F405
from __future__ import annotations
from typing import Any
from ._feedback_0 import *
from ._feedback_1 import *


def _merge_stored(stored: Any, record: dict[str, Any]) -> dict[str, Any]:
    merged = dict(record)
    if stored is None:
        return merged
    if isinstance(stored, dict):
        merged.update({key: value for key, value in stored.items() if value is not None})
        return merged
    if hasattr(stored, 'model_dump'):
        try:
            dumped = stored.model_dump()
            if isinstance(dumped, dict):
                merged.update({key: value for key, value in dumped.items() if value is not None})
                return merged
        except Exception:
            pass
    if hasattr(stored, 'dict'):
        try:
            dumped = stored.dict()
            if isinstance(dumped, dict):
                merged.update({key: value for key, value in dumped.items() if value is not None})
                return merged
        except Exception:
            pass
    for attr in (
        'feedback_id',
        'id',
        'rating',
        'reason',
        'citation_reference',
        'citation',
        'company_id',
        'role',
        'user_id',
        'thread_id',
        'answer_id',
        'status',
        'created_at',
    ):
        value = getattr(stored, attr, None)
        if value is not None:
            merged[attr] = value
    # Preserve any aliases returned too.
    for alias in _ID_ALIASES + _CITATION_ALIASES + _RATING_ALIASES + _REASON_ALIASES:
        value = getattr(stored, alias, None) if not isinstance(stored, dict) else stored.get(alias)
        if value is not None:
            merged[alias] = value
    # Canonicalise returned identifiers so callers using either alias see them.
    stored_id = None
    if isinstance(stored, dict):
        for alias in _ID_ALIASES:
            if stored.get(alias) is not None:
                stored_id = stored.get(alias)
                break
    else:
        for alias in _ID_ALIASES:
            val = getattr(stored, alias, None)
            if val is not None:
                stored_id = val
                break
    if stored_id is not None:
        for alias in _ID_ALIASES:
            merged[alias] = stored_id
    return merged


async def _repository_store(repo: Any, record: dict[str, Any], data: dict[str, Any]) -> Any:
    method_names = (
        'save_feedback',
        'store_feedback',
        'create_feedback',
        'submit_feedback',
        'record_feedback',
        'add_feedback',
        'insert_feedback',
        'put_feedback',
        'write_feedback',
        'report_wrong_source',
        'report',
        'save',
        'store',
        'create',
        'add',
        'insert',
        'put',
        'write',
        'append',
        'record',
        'submit',
        'persist',
        'upsert',
        'run',
        'execute',
        'handle',
        'invoke',
        'call',
    )
    extra = {k: v for k, v in data.items() if k not in {'action'}}
    attempts: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
    for method_name in method_names:
        attempts.extend(
            [
                (method_name, (record,), {}),
                (method_name, (), dict(record)),
                (method_name, (), {'feedback': record, **extra}),
                (method_name, (), {'feedback_record': record, **extra}),
                (method_name, (), {'data': record, **extra}),
                (method_name, (), {'payload': record, **extra}),
                (method_name, (), {'body': record, **extra}),
                (method_name, (), {'input': record, **extra}),
                (method_name, (), {'record': record, **extra}),
                (
                    method_name,
                    (),
                    {
                        'company_id': record.get('company_id'),
                        'user_id': record.get('user_id'),
                        'role': record.get('role'),
                        'rating': record.get('rating'),
                        'reason': record.get('reason'),
                        'citation_reference': record.get('citation_reference'),
                        **extra,
                    },
                ),
            ]
        )
    attempts.extend(
        [
            ('run', (record,), {}),
            ('execute', (record,), {}),
            ('handle', (record,), {}),
            ('__call__', (record,), {}),
        ]
    )
    if hasattr(repo, '__call__'):
        attempts.append(('__call__', (record,), {}))

    seen: set[str] = set()
    for method_name, positional, kwargs in attempts:
        key = f'{method_name}:{positional}:{sorted(kwargs.keys())}'
        if key in seen:
            continue
        seen.add(key)
        method = getattr(repo, method_name, None)
        if not callable(method):
            continue
        try:
            result = method(*positional, **_strip_empty(kwargs))
        except TypeError:
            try:
                result = method(*positional, **{k: v for k, v in kwargs.items() if v is not None})
            except Exception:
                continue
            except Exception:
                continue
        try:
            result = await _await(result)
        except Exception:
            continue
        return result
    return None


def _strip_empty(mapping: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if value is not None}


__all__ = ['_merge_stored', '_repository_store', '_strip_empty']
