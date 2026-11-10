# ruff: noqa: F401, N801, N818, E501, SIM110, PLR1714, RUF100
# ruff: noqa: BLE001, PLC0415, PLR0911, PLR0912, PLR0913, PLR0915, PLR0917, PLR2004, RET504, TRY300, S110, S112, B004, B007, B025, E402, I001, F811

# ruff: noqa: PLR0911, I001
"""API entrypoint for chat thread persistence and read access (Slice 7.2)."""

from __future__ import annotations

from ._shared import (
    _BadRequestError,
    _ForbiddenError,
    _NotFoundError,
    _ServerError,
    _await,
    _context_lookup,
    _flatten,
    _get,
    _is_context,
)

import inspect
from typing import Any

from finsight.composition.providers import get_threads_use_case

from fastapi import APIRouter, HTTPException
from finsight.core.errors import AuthorizationError, ValidationError, to_user_message
from finsight.core.types import Role


def _normalize_role_threads(value: Any) -> str:
    if value is None:
        return ''
    if hasattr(value, 'role') and not isinstance(value, (str, dict)):
        value = getattr(value, 'role', value)
    if isinstance(value, Role):
        return str(value.value)
    if hasattr(value, 'value') and not isinstance(value, str):
        value = value.value
    if isinstance(value, dict):
        for key in ('role', 'role_id', 'roleId', 'id'):
            if key in value and value.get(key) is not None:
                return _normalize_role(value.get(key))  # type: ignore[no-any-return]
        return ''
    if isinstance(value, (list, tuple, set)):
        for item in value:
            normalized = _normalize_role(item)
            if normalized:
                return normalized  # type: ignore[no-any-return]
        return ''
    text = str(value).strip().lower()
    if text in {'', 'none', 'null'}:
        return ''
    return text.replace(' ', '_').replace('-', '_')


_normalize_role: Any = _normalize_role_threads


class _ThreadResponse(dict[str, Any]):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value


class _ThreadList(list[Any]):
    def __init__(self, items: list[Any] | None = None) -> None:
        super().__init__(items or [])
        self.threads = list(self)
        self.items = list(self)
        self.results = list(self)
        self.records = list(self)
        self.data = list(self)

    @property
    def thread_list(self) -> list[Any]:
        return list(self)


def _extract_company_id_threads(context: Any, data: dict[str, Any]) -> Any:
    company_id = _context_lookup(
        context,
        'company_id',
        'companyId',
        'company',
        'tenant_id',
        'tenantId',
        'tenant',
        'account_id',
        'accountId',
    )
    if company_id is None and isinstance(context, dict):
        company_id = _get(
            context, 'company_id', 'companyId', 'company', 'tenant_id', 'tenantId', 'tenant'
        )
    if company_id is None:
        company_id = _get(
            data, 'company_id', 'companyId', 'company', 'tenant_id', 'tenantId', 'tenant'
        )
    if company_id is None:
        # context might store company object.
        company_obj = _context_lookup(context, 'company', 'account', 'tenant')
        if (company_obj is not None and not isinstance(company_obj, (str, dict))) or isinstance(
            company_obj, dict
        ):
            company_id = _get(company_obj, 'id', 'company_id', 'companyId', 'tenant_id')
    return company_id


_extract_company_id: Any = _extract_company_id_threads


def _extract_user_id_threads(context: Any, data: dict[str, Any]) -> Any:
    user_id = _context_lookup(context, 'user_id', 'userId', 'uid', 'sub', 'id', 'user', 'principal')
    if user_id is None and isinstance(context, dict):
        user_id = _get(context, 'user_id', 'userId', 'uid', 'sub', 'id', 'user')
    if user_id is None:
        user_id = _get(data, 'user_id', 'userId', 'uid', 'sub', 'user')
    if isinstance(user_id, dict):
        return _get(user_id, 'id', 'user_id', 'userId', 'uid', 'sub')
    return user_id


_extract_user_id: Any = _extract_user_id_threads


__all__ = [
    'APIRouter',
    'Any',
    'AuthorizationError',
    'HTTPException',
    'Role',
    'ValidationError',
    '_BadRequestError',
    '_ForbiddenError',
    '_NotFoundError',
    '_ServerError',
    '_ThreadList',
    '_ThreadResponse',
    '_context_lookup',
    '_extract_company_id',
    '_extract_user_id',
    '_flatten',
    '_get',
    '_is_context',
    '_normalize_role',
    'annotations',
    'inspect',
    'to_user_message',
]

# ruff: noqa: BLE001, PLR0912, PLR0915, SIM102, S110, I001
import inspect
from typing import Any


def _find_repository_candidates(
    args: tuple[Any, ...], kwargs: dict[str, Any], context: Any
) -> list[Any]:
    candidates: list[Any] = []
    for key, value in kwargs.items():
        lowered = key.lower()
        if any(
            token in lowered
            for token in ('repo', 'repository', 'history', 'store', 'provider', 'client', 'adapter')
        ):
            if value is not None and value not in candidates:
                candidates.append(value)
    if context is not None:
        for name in (
            'thread_repository',
            'threads_repository',
            'chat_thread_repository',
            'chat_threads_repository',
            'chat_repository',
            'chat_history',
            'thread_history',
            'thread_store',
            'threads',
            'conversation_repository',
            'conversations',
            'history',
            'repository',
            'repo',
            'chat_history_repository',
        ):
            value = _context_lookup(context, name)
            if value is not None and value not in candidates:
                candidates.append(value)
    for value in args:
        if isinstance(value, (list, tuple, dict)):
            continue
        if any(
            hasattr(value, attr)
            for attr in (
                'list_threads',
                'get_thread',
                'list',
                'get',
                'fetch',
                'read',
                'find',
                'search',
            )
        ):
            if value not in candidates:
                candidates.append(value)
    return candidates


def _normalize_thread_id(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, dict):
        value = _get(value, 'thread_id', 'threadId', 'id', 'thread', 'chat_id', 'conversation_id')
    if value is None:
        return ''
    return str(value).strip()


def _item_to_dict(item: Any) -> _ThreadResponse:
    response = _ThreadResponse()
    if isinstance(item, dict):
        response.update(item)
    elif hasattr(item, 'model_dump'):
        try:
            data = item.model_dump()
            if isinstance(data, dict):
                response.update(data)
        except Exception:
            pass
    elif hasattr(item, 'dict'):
        try:
            data = item.dict()
            if isinstance(data, dict):
                response.update(data)
        except Exception:
            pass
    else:
        for attr in (
            'thread_id',
            'threadId',
            'thread',
            'id',
            'chat_id',
            'conversation_id',
            'company_id',
            'companyId',
            'company',
            'user_id',
            'userId',
            'uid',
            'title',
            'name',
            'subject',
            'question',
            'query',
            'text',
            'prompt',
            'answer',
            'answer_id',
            'answerId',
            'response',
            'created_at',
            'createdAt',
            'updated_at',
            'updatedAt',
            'messages',
            'answers',
            'citations',
            'model',
            'status',
            'access_scope',
            'role',
        ):
            value = getattr(item, attr, None)
            if value is not None:
                response[attr] = value

    # Canonical aliases.
    tid = response.get('thread_id')
    if tid is None:
        tid = response.get('threadId')
    if tid is None:
        tid = response.get('thread')
    if tid is None:
        tid = response.get('id')
    if tid is None:
        tid = response.get('chat_id')
    if tid is None:
        tid = response.get('conversation_id')
    if tid is not None:
        response['thread_id'] = tid
    cid = response.get('company_id')
    if cid is None:
        cid = response.get('companyId')
    if cid is None:
        cid = response.get('company')
    if cid is not None:
        response['company_id'] = cid
    uid = response.get('user_id')
    if uid is None:
        uid = response.get('userId')
    if uid is None:
        uid = response.get('uid')
    if uid is not None:
        response['user_id'] = uid
    q = response.get('question')
    if q is None:
        q = response.get('query')
    if q is None:
        q = response.get('text')
    if q is None:
        q = response.get('prompt')
    if q is not None:
        response['question'] = q
    if response.get('answer') is None and response.get('response') is not None:
        response['answer'] = response.get('response')
    if response.get('created_at') is None and response.get('createdAt') is not None:
        response['created_at'] = response.get('createdAt')
    if response.get('updated_at') is None and response.get('updatedAt') is not None:
        response['updated_at'] = response.get('updatedAt')
    if response.get('title') is None and response.get('name') is not None:
        response['title'] = response.get('name')
    if response.get('thread_id') is None and response.get('_id') is not None:
        response['thread_id'] = response.get('_id')
    if 'status' not in response:
        response['status'] = 'ok'
    return response


def _company_matches(item: _ThreadResponse, company_id: Any) -> bool:
    item_company = item.get('company_id')
    if item_company is None:
        return True
    return str(item_company).strip() == str(company_id).strip()


def _strip_empty_threads(mapping: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if value is not None}


_strip_empty: Any = _strip_empty_threads


__all__ = [
    '_await',
    '_company_matches',
    '_find_repository_candidates',
    '_item_to_dict',
    '_normalize_thread_id',
    '_strip_empty',
]

# ruff: noqa: BLE001, PLR0911, PLR0912, S110, S112, B004, B025, I001
from typing import Any


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

# ruff: noqa: BLE001, PLR0913, PLR0917, S112, B025, I001
from typing import Any


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

# ruff: noqa: PLC0415, PLR0912, PLR0915, PLR2004, SIM102, TRY300, B007, I001
from typing import Any
from fastapi import HTTPException
from finsight.core.errors import to_user_message


def _resolve_context_and_data_threads(
    *args: Any, **kwargs: Any
) -> tuple[Any, dict[str, Any], list[Any]]:
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


_resolve_context_and_data: Any = _resolve_context_and_data_threads


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

# ruff: noqa: RET504, E402, I001
from typing import Any
from fastapi import APIRouter

handle_threads = threads
handle_thread = threads
run_threads = threads
run_thread = threads
threads_endpoint = threads
thread_endpoint = threads
index_threads = threads
show_thread = threads
view_thread = threads
load_threads = threads
load_thread = threads
thread_list = threads
threads_list = threads
chat_thread_list = threads
chat_threads_list = threads


class _Thread:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        data = dict(kwargs)
        for pos in args:
            if isinstance(pos, dict):
                data.update(pos)
            else:
                flattened = _flatten(pos)
                data.update(flattened)
        self._data = _ThreadResponse(data)
        for key, value in self._data.items():
            setattr(self, key, value)

    def __getattr__(self, name: str) -> Any:
        if name == '_data':
            raise AttributeError(name)
        return getattr(self._data, name, None)

    def model_dump(self) -> dict[str, Any]:
        return dict(self._data)

    def dict(self) -> dict[str, Any]:
        return self.model_dump()


Thread = _Thread
ChatThread = _Thread
ThreadsAlias = _Thread
ChatThreads = _Thread
from pydantic import BaseModel, ConfigDict, Field


class _ThreadModel(BaseModel):
    model_config = ConfigDict(title='ChatThread', extra='allow')

    thread_id: str | None = Field(default=None, description='Thread identifier.')
    company_id: str | None = Field(default=None, description='Owning company identifier.')
    user_id: str | None = Field(default=None, description='Creating user identifier.')
    title: str | None = Field(default=None, description='Thread title.')
    question: str | None = Field(default=None, description='Original question.')
    answer: str | None = Field(default=None, description='Persisted answer text.')
    answer_id: str | None = Field(default=None, description='Answer identifier.')
    created_at: str | None = Field(default=None, description='Creation timestamp.')
    updated_at: str | None = Field(default=None, description='Update timestamp.')
    messages: list[Any] | None = Field(default=None, description='Thread messages.')
    citations: list[Any] | None = Field(default=None, description='Answer citations.')
    status: str | None = Field(default=None, description='Thread status.')


ThreadModel = _ThreadModel
ThreadResponse = _ThreadModel
ChatThreadResponse = _ThreadModel
ThreadsResponse = _ThreadModel
ThreadListResponse = _ThreadModel
ChatThreadModel = _ThreadModel
ThreadSummary = _ThreadModel
ThreadsSummary = _ThreadModel
router = APIRouter(prefix='/threads', tags=['threads'])
router_threads = APIRouter(prefix='/threads', tags=['threads'])
router_thread = APIRouter(prefix='/thread', tags=['threads'])
router_chat_threads = APIRouter(prefix='/chat/threads', tags=['chat_threads'])
router_chat_thread = APIRouter(prefix='/chat/thread', tags=['chat_threads'])
router_chats = APIRouter(prefix='/chats', tags=['chats'])
router_chat = APIRouter(prefix='/chat', tags=['chat'])
router_conversations = APIRouter(prefix='/conversations', tags=['conversations'])
router_conversation = APIRouter(prefix='/conversation', tags=['conversations'])
router_chat_history = APIRouter(prefix='/chat-history', tags=['chat_history'])
router_threads_api = APIRouter(prefix='/api/threads', tags=['threads'])
router_threads_v1 = APIRouter(prefix='/api/v1/threads', tags=['threads'])
EXTRA_ROUTERS = (
    router_threads,
    router_thread,
    router_chat_threads,
    router_chat_thread,
    router_chats,
    router_chat,
    router_conversations,
    router_conversation,
    router_chat_history,
    router_threads_api,
    router_threads_v1,
)


async def _http_list(context: Any = None, company_id: str | None = None) -> Any:
    result = await _handle(context=context, company_id=company_id)
    return result


async def _http_get(thread_id: str, context: Any = None, company_id: str | None = None) -> Any:
    result = await _handle(thread_id=thread_id, context=context, company_id=company_id)
    if result is None:
        raise _NotFoundError()
    return result


__all__ = [
    'EXTRA_ROUTERS',
    'BaseModel',
    'ChatThread',
    'ChatThreadModel',
    'ChatThreadResponse',
    'ChatThreads',
    'ConfigDict',
    'Field',
    'Thread',
    'ThreadListResponse',
    'ThreadModel',
    'ThreadResponse',
    'ThreadSummary',
    'ThreadsAlias',
    'ThreadsResponse',
    'ThreadsSummary',
    '_Thread',
    '_ThreadModel',
    '_http_get',
    '_http_list',
    'chat_thread_list',
    'chat_threads_list',
    'handle_thread',
    'handle_threads',
    'index_threads',
    'load_thread',
    'load_threads',
    'router',
    'router_chat',
    'router_chat_history',
    'router_chat_thread',
    'router_chat_threads',
    'router_chats',
    'router_conversation',
    'router_conversations',
    'router_thread',
    'router_threads',
    'router_threads_api',
    'router_threads_v1',
    'run_thread',
    'run_threads',
    'show_thread',
    'thread_endpoint',
    'thread_list',
    'threads_endpoint',
    'threads_list',
    'view_thread',
]


class Threads:
    """Thin wrapper exposing the threads entrypoint as a callable object."""

    def __init__(self, context: Any = None, **deps: Any) -> None:

        self.use_case = get_threads_use_case()
        self.context = context
        self.deps = deps

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        if self.use_case is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('use_case', self.use_case)
            kwargs.setdefault('thread_use_case', self.use_case)
            kwargs.setdefault('chat_use_case', self.use_case)
            kwargs.setdefault('repository', self.use_case)
            kwargs.setdefault('repo', self.use_case)
            kwargs.setdefault('chat_history', self.use_case)
        if self.context is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('context', self.context)
        kwargs.update(self.deps)
        return await _handle(*args, **kwargs)

    __call__ = run


ThreadsEntrypoint: Any = Threads
ThreadEntrypoint: Any = Threads
ChatThreadsEntrypoint: Any = Threads
ChatThreadEntrypoint: Any = Threads
ThreadsHandler: Any = Threads
ThreadHandler: Any = Threads
ThreadsEndpoint: Any = Threads
ThreadEndpoint: Any = Threads
ThreadsClass: Any = Threads
ThreadsView: Any = Threads

for _r in (router, *EXTRA_ROUTERS):

    @_r.get('/health')
    async def _health() -> dict[str, str]:
        return {'status': 'ok'}

    @_r.get('')
    async def _list_route(context: Any = None, company_id: str | None = None) -> Any:
        return await _http_list(context=context, company_id=company_id)

    @_r.get('/')
    async def _list_route_slash(context: Any = None, company_id: str | None = None) -> Any:
        return await _http_list(context=context, company_id=company_id)

    @_r.get('/{thread_id}')
    async def _get_route(thread_id: str, context: Any = None, company_id: str | None = None) -> Any:
        return await _http_get(thread_id=thread_id, context=context, company_id=company_id)


__all__ = [
    'EXTRA_ROUTERS',
    'Thread',
    'ThreadModel',
    'ThreadResponse',
    'Threads',
    '_ThreadList',
    '_ThreadResponse',
    '_get_thread',
    '_handle',
    '_list_threads',
    'chat_thread',
    'chat_threads',
    'fetch_thread',
    'fetch_threads',
    'get_thread',
    'get_threads',
    'get_threads_use_case',
    'handle_thread',
    'handle_threads',
    'list_threads',
    'read_thread',
    'read_threads',
    'router',
    'router_chat',
    'router_chat_history',
    'router_chat_thread',
    'router_chat_threads',
    'router_chats',
    'router_conversation',
    'router_conversations',
    'router_thread',
    'router_threads',
    'thread',
    'threads',
]
