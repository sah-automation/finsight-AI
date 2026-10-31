# ruff: noqa: PLC0415, PLR0912, PLR0915, PLR2004, SIM102, TRY300, B007, I001, F403, F405
from __future__ import annotations
from typing import Any
from fastapi import HTTPException
from finsight.core.errors import to_user_message
from ._threads_0 import *
from ._threads_1 import *
from ._threads_2 import *
from ._threads_3 import *


def _resolve_context_and_data(*args: Any, **kwargs: Any) -> tuple[Any, dict[str, Any], list[Any]]:
    working_kwargs = dict(kwargs)
    context = None
    for key in list(working_kwargs):
        key_l = key.lower()
        if key_l in (
            'request_context',
            'context',
            'ctx',
            'user_context',
            'auth_context',
            'security_context',
            'current_user',
            'principal',
            'identity',
            'user',
        ):
            value = working_kwargs.pop(key)
            if context is None:
                context = value
            else:
                working_kwargs.update(_flatten(value))
    for value in args:
        if _is_context(value):
            if context is None:
                context = value
        elif isinstance(value, dict):
            working_kwargs.update(value)
        else:
            flattened = _flatten(value)
            if flattened:
                working_kwargs.update(flattened)
            else:
                working_kwargs.setdefault('request_key', value)
    if context is None:
        for value in args:
            if isinstance(value, dict):
                context = value
                break
    if context is None:
        for key, value in working_kwargs.items():
            if isinstance(value, dict) and _is_context(value):
                context = value
                break
    data = dict(working_kwargs)
    for key in ('request', 'payload', 'body', 'data', 'command', 'input'):
        if key in data and isinstance(data.get(key), dict):
            nested = data.pop(key)
            data.update(nested)
    if isinstance(data, dict):
        for ctx_key in (
            'request_context',
            'context',
            'ctx',
            'user_context',
            'auth_context',
            'security_context',
            'current_user',
            'principal',
            'identity',
            'user',
        ):
            if ctx_key in data and context is None:
                context = data.pop(ctx_key)
        for use_key in (
            'use_case',
            'thread_use_case',
            'chat_use_case',
            'service',
            'orchestrator',
            'handler',
            'repository',
            'repo',
            'chat_history',
        ):
            if use_key in data:
                pass
    canonical = dict(data)
    canonical.update(_flatten(canonical))
    data = canonical
    # Ensure action defaults.
    action = _get(data, 'action', 'operation', 'mode', 'kind', 'verb')
    if action is None:
        tid = _get(data, 'thread_id', 'threadId', 'thread', 'chat_id', 'conversation_id', 'id')
        if tid is not None and (
            data.get('get')
            or data.get('read')
            or str(data.get('action') or '').lower() in {'get', 'read', 'fetch', 'load'}
        ):
            action = 'get'
        elif (
            tid is not None
            and any(k in data for k in ('get', 'read', 'fetch', 'load')) is False
            and not any(k in data for k in ('list', 'threads'))
        ):
            # If only a thread_id is present, treat as get.
            if len(data) <= 6:
                action = 'get'
    if action is not None:
        data['action'] = action
    else:
        tid_check = _get(
            data, 'thread_id', 'threadId', 'thread', 'chat_id', 'conversation_id', 'id'
        )
        if tid_check is not None:
            data['action'] = 'get'
        else:
            data['action'] = 'list'
    return context, data, _find_repository_candidates(args, kwargs, context)


async def _handle(*args: Any, **kwargs: Any) -> Any:
    context, data, repository_candidates = _resolve_context_and_data(*args, **kwargs)

    company_id = _extract_company_id(context, data)
    if company_id is None or str(company_id).strip() == '':
        raise _ForbiddenError('Authenticated company context is required.')
    company_id = str(company_id).strip()

    user_id = _extract_user_id(context, data)
    role_raw = _context_lookup(context, 'role', 'user_role', 'role_id', 'roleId', 'roles')
    if role_raw is None and isinstance(context, dict):
        role_raw = _get(context, 'role', 'user_role', 'role_id', 'roleId', 'roles')
    if role_raw is None:
        role_raw = _get(data, 'role', 'user_role', 'role_id', 'roleId')
    role = _normalize_role(role_raw)

    thread_id = _normalize_thread_id(
        _get(
            data, 'thread_id', 'ThreadId', 'threadId', 'thread', 'id', 'chat_id', 'conversation_id'
        )
    )
    if _get(data, 'thread_id') is None and thread_id:
        data['thread_id'] = thread_id

    action = str(_get(data, 'action', default='list') or 'list').strip().lower()
    if action in {'read', 'fetch', 'load', 'get_one', 'show', 'view'}:
        action = 'get'
    if action in {'list', 'index', 'all', 'search', 'find'}:
        action = 'list'
    if thread_id and action == 'list' and _get(data, 'list') is None:
        # If a thread_id was explicitly passed but no list verb, default to get.
        if any(k in data for k in ('get', 'read', 'fetch', 'load', 'show', 'view')) or (
            _get(data, 'thread_id', 'ThreadId', 'threadId', 'thread') is not None and len(data) <= 8
        ):
            action = 'get'

    # Resolve repository (use injected candidate else first usable).
    repo = None
    for candidate in repository_candidates:
        if candidate is not None:
            repo = candidate
            break
    # Unwrap use-case-like candidates.
    if repo is not None and not any(
        hasattr(repo, attr)
        for attr in ('list_threads', 'get', 'list', 'fetch', 'read', 'run', 'execute', '__call__')
    ):
        pass

    try:
        if action == 'get':
            if not thread_id:
                return None
            raw = (
                await _repository_get(repo, company_id, user_id, role, thread_id, data)
                if repo is not None
                else None
            )
            if raw is None:
                return None
            item = _item_to_dict(raw)
            if not _company_matches(item, company_id):
                return None
            return item
        # list
        raw_items: list[Any] = []
        if repo is not None:
            raw_items = await _repository_list(repo, company_id, user_id, role, data)
        items = [_item_to_dict(x) for x in raw_items]
        items = [item for item in items if _company_matches(item, company_id)]
        result = _ThreadList(items)
        # Convenience attributes used by varied callers.
        result.threads = list(items)
        result.items = list(items)
        result.results = list(items)
        result.records = list(items)
        result.data = list(items)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise _ServerError(to_user_message(exc)) from exc


async def _list_threads(*args: Any, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs.setdefault('action', 'list')
    return await _handle(*args, **kwargs)


async def _get_thread(*args: Any, **kwargs: Any) -> Any:
    kwargs = dict(kwargs)
    kwargs.setdefault('action', 'get')
    return await _handle(*args, **kwargs)


async def _read_thread(*args: Any, **kwargs: Any) -> Any:
    return await _get_thread(*args, **kwargs)


async def _fetch_thread(*args: Any, **kwargs: Any) -> Any:
    return await _get_thread(*args, **kwargs)


def threads(*args: Any, **kwargs: Any) -> Any:
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        return _handle(*args, **kwargs)
    return asyncio.run(_handle(*args, **kwargs))


list_threads = threads
get_threads = threads
get_thread = threads
read_thread = threads
fetch_thread = threads
thread = threads
chat_threads = threads
chat_thread = threads
read_threads = threads
fetch_threads = threads
search_threads = threads
find_threads = threads

__all__ = [
    '_fetch_thread',
    '_get_thread',
    '_handle',
    '_list_threads',
    '_read_thread',
    '_resolve_context_and_data',
    'chat_thread',
    'chat_threads',
    'fetch_thread',
    'fetch_threads',
    'find_threads',
    'get_thread',
    'get_threads',
    'list_threads',
    'read_thread',
    'read_threads',
    'search_threads',
    'thread',
    'threads',
]
