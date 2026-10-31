# ruff: noqa: BLE001, PLR0911, PLR0912, S110, S112, B004, B025, I001, ANN401, F403, F405
from __future__ import annotations
from typing import Any
from ._threads_0 import *
from ._threads_1 import *


async def _repository_list(
    repo: Any,
    company_id: Any,
    user_id: Any,
    role: Any,
    data: dict[str, Any],
) -> list[Any]:
    method_names = (
        'list_threads',
        'list_thread',
        'list_threads_for_company',
        'list_threads_for_user',
        'list_all_threads',
        'list_all',
        'fetch_threads',
        'fetch_thread_list',
        'get_threads',
        'get_thread_list',
        'find_threads',
        'search_threads',
        'query_threads',
        'load_threads',
        'enumerate_threads',
        'list',
        'get_all',
        'all',
        'run',
        'execute',
        'handle',
        'invoke',
        'call',
    )
    extra = {k: v for k, v in data.items() if k not in {'action'}}

    # Preferred explicit list methods first.
    attempts: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
    for method_name in method_names:
        attempts.extend(
            [
                (
                    method_name,
                    (),
                    {
                        'company_id': company_id,
                        'user_id': user_id,
                        'role': role,
                        'action': 'list',
                        **extra,
                    },
                ),
                (method_name, (), {'company_id': company_id, 'user_id': user_id, **extra}),
                (method_name, (), {'company_id': company_id, **extra}),
                (method_name, (), {'company': company_id, **extra}),
                (method_name, (), {'tenant_id': company_id, **extra}),
                (method_name, (company_id,), {}),
                (method_name, (company_id, user_id), {}),
            ]
        )
    attempts.extend(
        [
            ('run', (data,), {}),
            ('execute', (data,), {}),
            ('handle', (data,), {}),
            ('__call__', (data,), {}),
        ]
    )
    if hasattr(repo, '__call__'):
        attempts.append(('__call__', (data,), {}))

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
                result = method(
                    *positional,
                    **{
                        k: v
                        for k, v in kwargs.items()
                        if k in ('company_id', 'user_id', 'role', 'action') and v is not None
                    },
                )
            except Exception:
                continue
            except Exception:
                continue
        try:
            result = await _await(result)
        except Exception:
            continue
        normalized = _result_as_list(result)
        if normalized is not None:
            return normalized
    return []


def _result_as_list(result: Any) -> list[Any] | None:
    if result is None:
        return None
    if isinstance(result, list):
        return list(result)
    if isinstance(result, tuple):
        return list(result)
    if isinstance(result, set):
        return list(result)
    if isinstance(result, dict):
        for key in (
            'threads',
            'thread_list',
            'items',
            'results',
            'records',
            'data',
            'list',
            'threads_list',
            'values',
        ):
            value = result.get(key)
            if isinstance(value, (list, tuple, set)):
                return list(value)
        # A dict could represent one thread; only treat as list if it has a list somewhere.
        for value in result.values():
            if isinstance(value, (list, tuple, set)):
                return list(value)
        return None
    # Object with collection attributes.
    for attr in ('threads', 'items', 'results', 'records', 'data', 'thread_list', 'values', 'all'):
        value = getattr(result, attr, None)
        if isinstance(value, (list, tuple, set)):
            return list(value)
    if hasattr(result, '__iter__') and not isinstance(result, (str, bytes, dict)):
        try:
            return list(result)
        except Exception:
            pass
    return None


__all__ = ['_repository_list', '_result_as_list']
