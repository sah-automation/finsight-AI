# ruff: noqa: BLE001, PLR0912, S112, B025, I001, F403, F405
from __future__ import annotations
from typing import Any
from ._feedback_0 import *
from ._feedback_1 import *
from ._feedback_2 import *


async def _repository_list(repo: Any, company_id: Any, data: dict[str, Any]) -> list[Any]:
    method_names = (
        'list_feedback',
        'list_feedbacks',
        'get_feedback',
        'get_feedbacks',
        'fetch_feedback',
        'fetch_feedbacks',
        'find_feedback',
        'find_feedbacks',
        'search_feedback',
        'search_feedbacks',
        'load_feedback',
        'load_feedbacks',
        'query_feedback',
        'query_feedbacks',
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
    attempts: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
    for method_name in method_names:
        attempts.extend(
            [
                (method_name, (), {'company_id': company_id, **extra}),
                (method_name, (), {'company': company_id, **extra}),
                (method_name, (), {'tenant_id': company_id, **extra}),
                (method_name, (company_id,), {}),
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
    collected: list[Any] = []
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
                    **{k: v for k, v in kwargs.items() if k in ('company_id',) and v is not None},
                )
            except Exception:
                continue
            except Exception:
                continue
        try:
            result = await _await(result)
        except Exception:
            continue
        # normalize
        normalized = None
        if isinstance(result, list):
            normalized = result
        elif isinstance(result, tuple):
            normalized = list(result)
        elif isinstance(result, dict):
            for keyname in (
                'feedbacks',
                'feedback',
                'items',
                'results',
                'records',
                'data',
                'list',
                'values',
            ):
                value = result.get(keyname)
                if isinstance(value, (list, tuple)):
                    normalized = list(value)
                    break
            if normalized is None:
                for value in result.values():
                    if isinstance(value, (list, tuple)):
                        normalized = list(value)
                        break
        if normalized is not None:
            collected = normalized
            break
        # single object for get attempt with id provided
        if (
            not isinstance(result, (list, tuple))
            and result is not None
            and _get(data, 'feedback_id', 'id')
        ):
            collected = [result]
            break
    return collected


def _company_matches(item: Any, company_id: Any) -> bool:
    item_company = None
    if isinstance(item, dict):
        item_company = (
            item.get('company_id')
            or item.get('companyId')
            or item.get('company')
            or item.get('tenant_id')
        )
    else:
        item_company = getattr(item, 'company_id', None) or getattr(item, 'companyId', None)
    if item_company is None:
        return False
    return str(item_company).strip() == str(company_id).strip()


__all__ = ['_company_matches', '_repository_list']
