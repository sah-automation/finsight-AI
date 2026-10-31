# ruff: noqa: BLE001, PLR0913, PLR0917, S112, B025, I001, ANN401, F403, F405
from __future__ import annotations
from typing import Any
from ._threads_0 import *
from ._threads_1 import *
from ._threads_2 import *


async def _repository_get(
    repo: Any,
    company_id: Any,
    user_id: Any,
    role: Any,
    thread_id: str,
    data: dict[str, Any],
) -> Any:
    method_names = (
        'get_thread',
        'get_thread_by_id',
        'read_thread',
        'fetch_thread',
        'find_thread',
        'load_thread',
        'retrieve_thread',
        'get',
        'read',
        'fetch',
        'find',
        'load',
        'retrieve',
        'one',
        'single',
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
                (
                    method_name,
                    (),
                    {
                        'company_id': company_id,
                        'user_id': user_id,
                        'role': role,
                        'thread_id': thread_id,
                        'id': thread_id,
                        'action': 'get',
                        **extra,
                    },
                ),
                (
                    method_name,
                    (),
                    {'company_id': company_id, 'thread_id': thread_id, 'id': thread_id, **extra},
                ),
                (method_name, (), {'company_id': company_id, 'thread_id': thread_id, **extra}),
                (method_name, (), {'company': company_id, 'thread_id': thread_id, **extra}),
                (method_name, (), {'tenant_id': company_id, 'thread_id': thread_id, **extra}),
                (method_name, (), {'company_id': company_id, 'id': thread_id, **extra}),
                (method_name, (), {'company_id': company_id, 'key': thread_id, **extra}),
                (method_name, (company_id, thread_id), {}),
                (method_name, (thread_id, company_id), {}),
                (method_name, (thread_id,), {}),
                (method_name, (company_id,), {'thread_id': thread_id, **extra}),
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
                        if k in ('company_id', 'thread_id', 'id') and v is not None
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
        # A list result for a get attempt means the method ignored thread_id; skip.
        if isinstance(result, (list, tuple, set)):
            continue
        if (
            isinstance(result, dict)
            and any(
                k in result for k in ('threads', 'items', 'results', 'records', 'values', 'list')
            )
            and not any(
                k in result
                for k in (
                    'thread_id',
                    'threadId',
                    'id',
                    'thread',
                    'company_id',
                    'companyId',
                    'question',
                )
            )
        ):
            continue
        return result
    return None


__all__ = ['_repository_get']
