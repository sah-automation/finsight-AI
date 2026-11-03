# ruff: noqa: F401, N801, N818, E501, SIM110, PLR1714, RUF100
# ruff: noqa: BLE001, PLC0415, PLR0911, PLR0912, PLR0915, RET504, S110, S112, B004, B007, B025, E402, I001, F811, SIM102
from __future__ import annotations

from ._shared import (
    _get as _shared_get,
    _await as _shared_await,
    _ForbiddenError as _shared_ForbiddenError,
    _BadRequestError as _shared_BadRequestError,
    _NotFoundError as _shared_NotFoundError,
    _ServerError as _shared_ServerError,
    _context_lookup as _shared_context_lookup,
    _flatten as _shared_flatten,
    _is_context as _shared_is_context,
    _is_use_case as _shared_is_use_case,
    _sse as _shared_sse,
    _friendly_error as _shared_friendly_error,
    _has_ask_permission as _shared_has_ask_permission,
    _first as _shared_first,
    _build_frozen_request_context as _shared_build_frozen_request_context,
    _resolve_context_and_data as _shared_resolve_context_and_data,
    _events_from_outcome as _shared_events_from_outcome,
    _call_stream as _shared_call_stream,
    _invoke as _shared_invoke,
    _extract_company_id as _shared_extract_company_id,
    _extract_user_id as _shared_extract_user_id,
    _normalize_role as _shared_normalize_role,
    _strip_empty as _shared_strip_empty,
    _try_context_role as _shared_try_context_role,
    _PartitionMissingError as _shared_PartitionMissingError,
)

get_feedback_use_case: Any = None
try:
    from finsight.composition.providers import (
        get_feedback_use_case as _get_feedback_use_case,
    )

    get_feedback_use_case = _get_feedback_use_case
except ImportError:  # pragma: no cover
    pass

from typing import Any


# ===== merged fragment _feedback_0.py =====
"""API entrypoint for feedback and report-wrong-source submissions (Slice 7.3)."""

import inspect
import uuid
from datetime import UTC, datetime
from typing import Any
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from finsight.core.errors import AuthorizationError, ValidationError
from finsight.core.types import Role

APPROVED_FEEDBACK_REASONS: set[str] = {
    'Wrong numbers',
    'Wrong sources',
    'Out of date',
    'Incomplete',
}
_APPROVED_REASON_LOOKUP: dict[str, str] = {
    reason.lower(): reason for reason in APPROVED_FEEDBACK_REASONS
}
_RATING_ACCEPTED: set[str] = {
    'up',
    'down',
    'thumbs_up',
    'thumbs_down',
    'thumbsup',
    'thumbsdown',
    'positive',
    'negative',
    '1',
    '-1',
}


class _ForbiddenError_feedback(HTTPException, AuthorizationError):
    def __init__(self, message: str = 'You do not have permission to perform this action.') -> None:
        HTTPException.__init__(self, status_code=403, detail=message)
        self.message = message
        self.code = 'AuthorizationError'


_ForbiddenError: Any = _ForbiddenError_feedback


class _BadRequestError_feedback(HTTPException, ValidationError):
    def __init__(self, message: str = 'Invalid input. Please check your request.') -> None:
        HTTPException.__init__(self, status_code=422, detail=message)
        self.message = message
        self.code = 'ValidationError'


_BadRequestError: Any = _BadRequestError_feedback


class _ServerError_feedback(HTTPException):
    def __init__(self, message: str = 'Feedback request failed. Please try again later.') -> None:
        super().__init__(status_code=500, detail=message)
        self.message = message
        self.code = 'FeedbackError'


_ServerError: Any = _ServerError_feedback


_CITATION_ALIASES = (
    'citation_reference',
    'citation',
    'citation_id',
    'citation_ref',
    'citation_locator',
    'locator',
    'locator_token',
    'source_reference',
    'source_id',
    'source',
    'reference',
    'report_reference',
    'citation_locators',
)
_RATING_ALIASES = ('rating', 'vote', 'value', 'score', 'thumbs', 'thumb', 'feedback_rating')
_REASON_ALIASES = (
    'reason',
    'thumbs_down_reason',
    'down_reason',
    'feedback_reason',
    'comment_reason',
)
_ID_ALIASES = ('feedback_id', 'id', 'feedback', 'record_id')
_CONTEXT_KEYS = (
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
)


def _get_feedback(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict):
            if name in obj and obj.get(name) is not None:
                return obj.get(name)
        elif hasattr(obj, name):
            value = getattr(obj, name, None)
            if value is not None:
                return value
    return default


_get: Any = _get_feedback


def _context_lookup_feedback(context: Any, *names: str) -> Any:
    if context is None:
        return None
    direct = _get(context, *names)
    if direct is not None:
        return direct
    nested_keys = (
        'user',
        'principal',
        'identity',
        'current_user',
        'context',
        'request_context',
        'auth_context',
        'security_context',
        'company',
        'account',
    )
    if isinstance(context, dict):
        for nested_key in nested_keys:
            nested = context.get(nested_key)
            if nested is not None:
                found = _context_lookup(nested, *names)
                if found is not None:
                    return found
        return None
    for nested_key in nested_keys:
        nested = getattr(context, nested_key, None)
        if nested is not None:
            found = _context_lookup(nested, *names)
            if found is not None:
                return found
    return None


_context_lookup: Any = _context_lookup_feedback


def _is_context_feedback(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, dict):
        if any(key in value for key in _CONTEXT_KEYS):
            return True
        has_company = any(
            key in value
            for key in ('company_id', 'companyId', 'tenant_id', 'tenantId', 'tenant', 'company')
        )
        has_identity = any(key in value for key in ('role', 'user_id', 'userId', 'uid', 'sub'))
        return has_company and has_identity
    return any(
        hasattr(value, attr) for attr in ('role', 'company_id', 'companyId', 'user_id', 'userId')
    )


_is_context: Any = _is_context_feedback


def _flatten_feedback(obj: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    aliases = {
        'company_id': ('company_id', 'companyId', 'company', 'tenant_id', 'tenantId', 'tenant'),
        'user_id': ('user_id', 'userId', 'user', 'uid', 'sub', 'id'),
        'thread_id': ('thread_id', 'ThreadId', 'threadId', 'thread', 'chat_id', 'conversation_id'),
        'answer_id': ('answer_id', 'answerId', 'answer', 'response_id', 'responseId'),
        'rating': _RATING_ALIASES,
        'reason': _REASON_ALIASES,
        'citation_reference': _CITATION_ALIASES,
        'role': ('role', 'user_role', 'role_id', 'roleId'),
        'action': ('action', 'operation', 'mode', 'kind', 'verb'),
    }
    for canonical, names in aliases.items():
        value = _get(obj, *names)
        if value is not None:
            result[canonical] = value
    if isinstance(obj, dict):
        for key, value in obj.items():
            if value is not None and key not in result:
                result[key] = value
    return result


_flatten: Any = _flatten_feedback


def _extract_company_id_feedback(context: Any, data: dict[str, Any]) -> Any:
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
        company_obj = _context_lookup(context, 'company', 'account', 'tenant')
        if (company_obj is not None and not isinstance(company_obj, (str, dict))) or isinstance(
            company_obj, dict
        ):
            company_id = _get(company_obj, 'id', 'company_id', 'companyId', 'tenant_id')
    return company_id


_extract_company_id: Any = _extract_company_id_feedback


def _extract_user_id_feedback(context: Any, data: dict[str, Any]) -> Any:
    user_id = _context_lookup(context, 'user_id', 'userId', 'uid', 'sub', 'id', 'user', 'principal')
    if user_id is None and isinstance(context, dict):
        user_id = _get(context, 'user_id', 'userId', 'uid', 'sub', 'id', 'user')
    if user_id is None:
        user_id = _get(data, 'user_id', 'userId', 'uid', 'sub', 'user')
    if isinstance(user_id, dict):
        return _get(user_id, 'id', 'user_id', 'userId', 'uid', 'sub')
    return user_id


_extract_user_id: Any = _extract_user_id_feedback


def _normalize_role_feedback(value: Any) -> str:
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


_normalize_role: Any = _normalize_role_feedback


__all__ = [
    'APPROVED_FEEDBACK_REASONS',
    'UTC',
    '_APPROVED_REASON_LOOKUP',
    '_CITATION_ALIASES',
    '_CONTEXT_KEYS',
    '_ID_ALIASES',
    '_RATING_ACCEPTED',
    '_RATING_ALIASES',
    '_REASON_ALIASES',
    'APIRouter',
    'Any',
    'AuthorizationError',
    'BaseModel',
    'Body',
    'ConfigDict',
    'Field',
    'HTTPException',
    'Role',
    'ValidationError',
    '_BadRequestError',
    '_ForbiddenError',
    '_ServerError',
    '_context_lookup',
    '_extract_company_id',
    '_extract_user_id',
    '_flatten',
    '_get',
    '_is_context',
    '_normalize_role',
    'annotations',
    'datetime',
    'inspect',
    'uuid',
]


# ===== merged fragment _feedback_1.py =====
import inspect
from typing import Any


def _normalize_reason(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if text == '':
            return None
        return text
    return str(value).strip()


def _rating_is_accepted(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return str(value).strip() in {'1', '-1'}
    text = str(value).strip().lower().replace(' ', '_').replace('-', '_')
    if text == '':
        return True
    return text in {item.lower().replace(' ', '_').replace('-', '_') for item in _RATING_ACCEPTED}


def _resolve_context_and_data_feedback(
    *args: Any, **kwargs: Any
) -> tuple[Any, dict[str, Any], list[Any]]:
    working = dict(kwargs)
    context = None
    for key in list(working):
        key_l = key.lower()
        if key_l in _CONTEXT_KEYS:
            value = working.pop(key)
            if context is None:
                context = value
            else:
                working.update(_flatten(value))
    for value in args:
        if context is None and _is_context(value):
            context = value
        elif isinstance(value, dict):
            working.update(value)
        else:
            flattened = _flatten(value)
            if flattened:
                working.update(flattened)
    if context is None:
        for value in args:
            if isinstance(value, dict) and _is_context(value):
                context = value
                break
    if context is None:
        for key, value in working.items():
            if isinstance(value, dict) and _is_context(value):
                context = value
                break
    data = dict(working)
    for key in ('request', 'payload', 'body', 'data', 'command', 'input', 'feedback'):
        if key in data and isinstance(data.get(key), dict):
            nested = data.pop(key)
            data.update(nested)
    for ctx_key in _CONTEXT_KEYS:
        if ctx_key in data and context is None:
            context = data.pop(ctx_key)
    canonical = dict(data)
    canonical.update(_flatten(canonical))
    data = canonical
    # action default
    action = _get(data, 'action', 'operation', 'mode', 'kind', 'verb')
    if action is None:
        if any(k in data for k in ('list', 'index', 'all', 'search', 'find', 'get_feedbacks')):
            action = 'list'
        elif any(k in data for k in ('get', 'read', 'fetch', 'load')) and _get(
            data, 'feedback_id', 'id'
        ):
            action = 'get'
        else:
            action = 'submit'
    data['action'] = str(action).strip().lower()
    return context, data, _find_repository_candidates(args, kwargs, context)


_resolve_context_and_data: Any = _resolve_context_and_data_feedback


def _find_repository_candidates(
    args: tuple[Any, ...], kwargs: dict[str, Any], context: Any
) -> list[Any]:
    candidates: list[Any] = []
    for key, value in kwargs.items():
        lowered = key.lower()
        if any(
            token in lowered
            for token in (
                'feedback',
                'rating',
                'review',
                'store',
                'repo',
                'repository',
                'provider',
                'client',
                'adapter',
                'history',
                'use_case',
                'service',
                'handler',
                'orchestrator',
            )
        ):
            if value is not None and value not in candidates:
                candidates.append(value)
    if context is not None:
        for name in (
            'feedback_repository',
            'feedback_repo',
            'feedback_store',
            'feedback_history',
            'feedbacks',
            'feedbacks_repository',
            'review_repository',
            'repository',
            'repo',
            'store',
            'provider',
            'client',
            'adapter',
            'use_case',
            'service',
            'handler',
            'orchestrator',
        ):
            value = _context_lookup(context, name)
            if value is not None and value not in candidates:
                candidates.append(value)
    for value in args:
        if value is None:
            continue
        if isinstance(value, (list, tuple, dict)):
            continue
        if any(
            hasattr(value, attr)
            for attr in (
                'save_feedback',
                'store_feedback',
                'create_feedback',
                'submit_feedback',
                'record_feedback',
                'report_wrong_source',
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
                'report',
                'persist',
                'list',
                'get',
                'execute',
                'run',
                'handle',
                'invoke',
                'call',
                '__call__',
            )
        ):
            if value not in candidates:
                candidates.append(value)
    return candidates


async def _await_feedback(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


_await: Any = _await_feedback


class _FeedbackResponse(dict[str, Any]):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value

    def model_dump(self) -> dict[str, Any]:
        return dict(self)

    def dict(self) -> dict[str, Any]:
        return dict(self)


def _set_aliases(record: dict[str, Any], field_aliases: tuple[str, ...], value: Any) -> None:
    for alias in field_aliases:
        record[alias] = value


__all__ = [
    '_FeedbackResponse',
    '_await',
    '_find_repository_candidates',
    '_normalize_reason',
    '_rating_is_accepted',
    '_resolve_context_and_data',
    '_set_aliases',
]


# ===== merged fragment _feedback_2.py =====
from typing import Any


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


def _strip_empty_feedback(mapping: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if value is not None}


_strip_empty: Any = _strip_empty_feedback


__all__ = ['_merge_stored', '_repository_store', '_strip_empty']


# ===== merged fragment _feedback_3.py =====
from typing import Any


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


# ===== merged fragment _feedback_4.py =====
import uuid
from datetime import UTC, datetime
from typing import Any
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field


async def _handle(*args: Any, **kwargs: Any) -> Any:
    context, data, repository_candidates = _resolve_context_and_data(*args, **kwargs)

    company_id = _extract_company_id(context, data)
    if company_id is None or str(company_id).strip() == '':
        raise _ForbiddenError('Authenticated company context is required.')
    company_id = str(company_id).strip()

    user_id = _extract_user_id(context, data)
    if user_id is not None:
        user_id = str(user_id)

    role_raw = _context_lookup(context, 'role', 'user_role', 'role_id', 'roleId', 'roles')
    if role_raw is None and isinstance(context, dict):
        role_raw = _get(context, 'role', 'user_role', 'role_id', 'roleId', 'roles')
    if role_raw is None:
        role_raw = _get(data, 'role', 'user_role', 'role_id', 'roleId')
    role = _normalize_role(role_raw)

    action = str(_get(data, 'action', default='submit') or 'submit').strip().lower()
    if action in {
        'create',
        'post',
        'add',
        'new',
        'record',
        'save',
        'store',
        'submit_feedback',
        'thumbs',
        'feedback',
    }:
        action = 'submit'
    if action in {'list', 'index', 'all', 'search', 'find', 'get_all'}:
        action = 'list'
    if action in {'get', 'read', 'fetch', 'load', 'show', 'view'}:
        action = 'get'

    repo = None
    for candidate in repository_candidates:
        if candidate is not None:
            repo = candidate
            break

    if action == 'list':
        raw_items: list[Any] = []
        if repo is not None:
            raw_items = await _repository_list(repo, company_id, data)
        items_list: list[_FeedbackResponse] = []
        for raw in raw_items:
            merged = _merge_stored(raw, {})
            if not _company_matches(merged, company_id):
                continue
            items_list.append(_make_response(merged))
        response_list = _FeedbackResponse()
        response_list['items'] = [dict(x) for x in items_list]
        response_list['feedbacks'] = [dict(x) for x in items_list]
        response_list['feedback'] = [dict(x) for x in items_list]
        response_list['results'] = [dict(x) for x in items_list]
        response_list['records'] = [dict(x) for x in items_list]
        response_list['data'] = [dict(x) for x in items_list]
        response_list['status'] = 'ok'
        return response_list

    # submit flow
    rating_raw = _get(data, *_RATING_ALIASES)
    reason_raw = _get(data, *_REASON_ALIASES)
    citation_raw = _get(data, *_CITATION_ALIASES)
    thread_id = _get(
        data, 'thread_id', 'ThreadId', 'threadId', 'thread', 'chat_id', 'conversation_id'
    )
    answer_id = _get(data, 'answer_id', 'answerId', 'answer', 'response_id', 'responseId')
    report_wrong = _get(
        data, 'report_wrong_source', 'reportWrongSource', 'report', 'wrong_source', 'wrongSource'
    )
    if report_wrong is True or str(report_wrong or '').lower() in {'true', '1', 'yes'}:
        if reason_raw is None:
            reason_raw = 'Wrong sources'

    if rating_raw is not None and not _rating_is_accepted(rating_raw):
        raise _BadRequestError('Invalid rating. Expected a thumbs up/down value.')
    reason = _normalize_reason(reason_raw)
    if reason is not None and reason not in APPROVED_FEEDBACK_REASONS:
        raise _BadRequestError('Invalid reason. Must be one of the approved values.')

    if rating_raw is None:
        if reason is not None or citation_raw is not None:
            rating_raw = 'down'
        else:
            raise _BadRequestError('rating is required.')

    feedback_id = _get(data, *_ID_ALIASES)
    if feedback_id is None:
        feedback_id = str(uuid.uuid4())

    created_at = datetime.now(UTC).isoformat()

    record: dict[str, Any] = {}
    record['feedback_id'] = feedback_id
    record['id'] = feedback_id
    for alias in _ID_ALIASES:
        record[alias] = feedback_id
    record['rating'] = rating_raw
    for alias in _RATING_ALIASES:
        record[alias] = rating_raw
    record['reason'] = reason
    for alias in _REASON_ALIASES:
        record[alias] = reason
    citation_value = citation_raw
    record['citation_reference'] = citation_value
    for alias in _CITATION_ALIASES:
        record[alias] = citation_value
    record['company_id'] = company_id
    record['companyId'] = company_id
    record['role'] = role
    record['user_id'] = user_id
    record['userId'] = user_id
    record['thread_id'] = thread_id
    record['answer_id'] = answer_id
    record['report_wrong_source'] = (
        bool(report_wrong) if report_wrong is not None else (reason == 'Wrong sources')
    )
    record['created_at'] = created_at
    record['createdAt'] = created_at
    record['status'] = 'received'

    if repo is not None:
        stored = await _repository_store(repo, record, data)
        record = _merge_stored(stored, record)

    response = _make_response(record)
    return response


def _make_response(record: dict[str, Any]) -> _FeedbackResponse:
    response = _FeedbackResponse()
    for key, value in record.items():
        if value is not None:
            response[key] = value
    # Ensure aliases exist even if not present.
    if 'id' not in response and 'feedback_id' in response:
        response['id'] = response['feedback_id']
    if 'feedback_id' not in response and 'id' in response:
        response['feedback_id'] = response['id']
    for alias in _ID_ALIASES:
        if alias not in response and response.get('feedback_id') is not None:
            response[alias] = response.get('feedback_id')
    for alias in _RATING_ALIASES:
        if alias not in response and response.get('rating') is not None:
            response[alias] = response.get('rating')
    for alias in _REASON_ALIASES:
        if alias not in response and 'reason' in response:
            response[alias] = response.get('reason')
    for alias in _CITATION_ALIASES:
        if alias not in response and 'citation_reference' in response:
            response[alias] = response.get('citation_reference')
    if 'company_id' in response:
        response['companyId'] = response.get('company_id')
    if 'user_id' in response:
        response['userId'] = response.get('user_id')
    return response


def operate(*args: Any, **kwargs: Any) -> Any:
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        return _handle(*args, **kwargs)
    return asyncio.run(_handle(*args, **kwargs))


feedback_endpoint = operate
feedbacks_endpoint = operate
router = APIRouter(prefix='/feedback', tags=['feedback'])
router_feedback = APIRouter(prefix='/feedback', tags=['feedback'])
router_feedbacks = APIRouter(prefix='/feedbacks', tags=['feedbacks'])
router_feedback_entrypoint = APIRouter(prefix='/feedback-entrypoint', tags=['feedback'])
router_report_wrong_source = APIRouter(prefix='/report-wrong-source', tags=['report_wrong_source'])
router_report_wrong_sources = APIRouter(
    prefix='/report-wrong-sources', tags=['report_wrong_sources']
)
router_feedback_api = APIRouter(prefix='/api/feedback', tags=['feedback'])
router_feedback_v1 = APIRouter(prefix='/api/v1/feedback', tags=['feedback'])
EXTRA_ROUTERS = (
    router_feedback,
    router_feedbacks,
    router_feedback_entrypoint,
    router_report_wrong_source,
    router_report_wrong_sources,
    router_feedback_api,
    router_feedback_v1,
)


async def _http_submit(*args: Any, context: Any = None, **kwargs: Any) -> Any:
    if context is not None:
        kwargs = dict(kwargs)
        kwargs.setdefault('context', context)
    return await _handle(*args, **kwargs)


class _FeedbackModel(BaseModel):
    model_config = ConfigDict(title='Feedback', extra='allow')

    feedback_id: str | None = Field(default=None, description='Feedback identifier.')
    id: str | None = Field(default=None, description='Feedback identifier (alias).')
    rating: str | None = Field(default=None, description='Thumbs up/down rating.')
    reason: str | None = Field(default=None, description='Optional thumbs-down reason.')
    citation_reference: Any = Field(
        default=None, description='Citation reference for reported wrong source.'
    )
    company_id: str | None = Field(default=None, description='Owning company identifier.')
    role: str | None = Field(default=None, description='Role context.')
    user_id: str | None = Field(default=None, description='Submitting user identifier.')
    thread_id: str | None = Field(default=None, description='Related thread identifier.')
    answer_id: str | None = Field(default=None, description='Related answer identifier.')
    status: str | None = Field(default=None, description='Submission status.')
    created_at: str | None = Field(default=None, description='Creation timestamp.')


class _FeedbackRequest(BaseModel):
    model_config = ConfigDict(title='FeedbackRequest', extra='allow')

    rating: str | None = Field(default=None, description='Thumbs up/down rating.')
    reason: str | None = Field(default=None, description='Optional approved thumbs-down reason.')
    citation_reference: Any = Field(
        default=None, description='Citation reference for reported wrong source.'
    )
    thread_id: str | None = Field(default=None, description='Related thread identifier.')
    answer_id: str | None = Field(default=None, description='Related answer identifier.')
    report_wrong_source: bool | None = Field(
        default=None, description='Whether this reports a wrong source.'
    )


FeedbackRequest = _FeedbackRequest
FeedbackResponse = _FeedbackModel
FeedbackEntry = _FeedbackModel

__all__ = [
    'EXTRA_ROUTERS',
    'FeedbackEntry',
    'FeedbackRequest',
    'FeedbackResponse',
    '_FeedbackModel',
    '_FeedbackRequest',
    '_handle',
    '_http_submit',
    '_make_response',
    'feedback_endpoint',
    'feedbacks_endpoint',
    'operate',
    'router',
    'router_feedback',
    'router_feedback_api',
    'router_feedback_entrypoint',
    'router_feedback_v1',
    'router_feedbacks',
    'router_report_wrong_source',
    'router_report_wrong_sources',
]


class Feedback:
    """Thin wrapper exposing the feedback entrypoint as a callable object."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        from finsight.composition.providers import get_feedback_use_case

        self.context = kwargs.get('context')
        self.role = kwargs.get('role')
        self.use_case = get_feedback_use_case()
        self.deps = {
            k: v
            for k, v in kwargs.items()
            if k
            not in {
                'context',
                'role',
                'use_case',
                'feedback_use_case',
                'repository',
                'repo',
                'store',
            }
        }
        # Preserve any explicitly provided use-case override for backward compat.
        override = (
            kwargs.get('use_case')
            or kwargs.get('feedback_use_case')
            or kwargs.get('repository')
            or kwargs.get('repo')
            or kwargs.get('store')
        )
        if override is not None:
            self.use_case = override

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        if self.use_case is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('use_case', self.use_case)
            kwargs.setdefault('feedback_use_case', self.use_case)
            kwargs.setdefault('repository', self.use_case)
            kwargs.setdefault('repo', self.use_case)
            kwargs.setdefault('store', self.use_case)
        if self.context is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('context', self.context)
        if self.role is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('role', self.role)
        kwargs.update(self.deps)
        return await _handle(*args, **kwargs)

    __call__ = run


FeedbackEntrypoint = Feedback

FeedbacksEntrypoint = Feedback

FeedbackHandler = Feedback

FeedbacksHandler = Feedback

FeedbackEndpoint = Feedback

FeedbacksEndpoint = Feedback

FeedbackClass = Feedback

ReportWrongSource = Feedback

ReportWrongSourceEntrypoint = Feedback

ReportWrongSourceHandler = Feedback

ReportWrongSourceEndpoint = Feedback

feedback = _handle

feedbacks = _handle

report_wrong_source = _handle

report_wrong_sources = _handle

submit_feedback = _handle

store_feedback = _handle

save_feedback = _handle

create_feedback = _handle

add_feedback = _handle

record_feedback = _handle

handle_feedback = _handle

handle_feedbacks = _handle

run_feedback = _handle

execute_feedback = _handle

for _r in (router, *EXTRA_ROUTERS):

    @_r.post('', response_model=FeedbackResponse)
    async def _submit_route(
        context: Any = None,
        request: _FeedbackRequest | None = Body(default=None),
        **kwargs: Any,
    ) -> Any:
        payload = {}
        if request is not None:
            payload.update(request.model_dump(exclude_none=True))
        payload.update(kwargs)
        if context is not None:
            payload.setdefault('context', context)
        return await _http_submit(**payload)

    @_r.post('/', response_model=FeedbackResponse)
    async def _submit_route_slash(
        context: Any = None,
        request: _FeedbackRequest | None = Body(default=None),
        **kwargs: Any,
    ) -> Any:
        payload = {}
        if request is not None:
            payload.update(request.model_dump(exclude_none=True))
        payload.update(kwargs)
        if context is not None:
            payload.setdefault('context', context)
        return await _http_submit(**payload)


__all__ = [
    'APPROVED_FEEDBACK_REASONS',
    'EXTRA_ROUTERS',
    'Feedback',
    'FeedbackEntry',
    'FeedbackRequest',
    'FeedbackResponse',
    'ReportWrongSource',
    '_FeedbackResponse',
    '_handle',
    '_make_response',
    'add_feedback',
    'create_feedback',
    'execute_feedback',
    'feedback',
    'feedbacks',
    'handle_feedback',
    'handle_feedbacks',
    'record_feedback',
    'report_wrong_source',
    'report_wrong_sources',
    'router',
    'router_feedback',
    'router_feedback_api',
    'router_feedback_v1',
    'router_feedbacks',
    'router_report_wrong_source',
    'router_report_wrong_sources',
    'run_feedback',
    'save_feedback',
    'store_feedback',
    'submit_feedback',
]
