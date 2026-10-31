# ruff: noqa: PLR0911, I001
"""API entrypoint for chat thread persistence and read access (Slice 7.2)."""

from __future__ import annotations
import inspect
from typing import Any
from fastapi import APIRouter, HTTPException
from finsight.core.errors import AuthorizationError, ValidationError, to_user_message
from finsight.core.types import Role


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict):
            if name in obj and obj.get(name) is not None:
                return obj.get(name)
        elif hasattr(obj, name):
            value = getattr(obj, name, None)
            if value is not None:
                return value
    return default


def _context_lookup(context: Any, *names: str) -> Any:
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
        'chat_history',
        'thread_repository',
        'threads',
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


def _is_context(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, dict):
        for key in (
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
            if key in value:
                return True
        for key in ('company_id', 'companyId', 'role', 'user_id', 'userId', 'thread_id'):
            if key in value:
                return True
        return False
    return any(
        hasattr(value, attr) for attr in ('role', 'company_id', 'companyId', 'user_id', 'userId')
    )


def _flatten(obj: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    aliases = {
        'company_id': ('company_id', 'companyId', 'company', 'tenant_id', 'tenantId', 'tenant'),
        'user_id': ('user_id', 'userId', 'user', 'uid', 'sub', 'id'),
        'thread_id': ('thread_id', 'ThreadId', 'threadId', 'thread', 'chat_id', 'conversation_id'),
        'title': ('title', 'name', 'subject'),
        'question': ('question', 'query', 'text', 'prompt'),
        'access_scope': ('access_scope', 'accessScope', 'scope', 'access', 'permission_scope'),
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


def _normalize_role(value: Any) -> str:
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
                return _normalize_role(value.get(key))
        return ''
    if isinstance(value, (list, tuple, set)):
        for item in value:
            normalized = _normalize_role(item)
            if normalized:
                return normalized
        return ''
    text = str(value).strip().lower()
    if text in {'', 'none', 'null'}:
        return ''
    return text.replace(' ', '_').replace('-', '_')


class _NotFoundError(HTTPException):
    def __init__(self, message: str = 'Thread not found.') -> None:
        super().__init__(status_code=404, detail=message)
        self.message = message
        self.code = 'NotFoundError'


class _ForbiddenError(HTTPException, AuthorizationError):
    def __init__(self, message: str = 'You do not have permission to perform this action.') -> None:
        HTTPException.__init__(self, status_code=403, detail=message)
        self.message = message
        self.code = 'AuthorizationError'


class _BadRequestError(HTTPException, ValidationError):
    def __init__(self, message: str = 'Invalid input. Please check your request.') -> None:
        HTTPException.__init__(self, status_code=422, detail=message)
        self.message = message
        self.code = 'ValidationError'


class _ServerError(HTTPException):
    def __init__(self, message: str = 'Thread request failed. Please try again later.') -> None:
        super().__init__(status_code=500, detail=message)
        self.message = message
        self.code = 'ThreadError'


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


def _extract_company_id(context: Any, data: dict[str, Any]) -> Any:
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


def _extract_user_id(context: Any, data: dict[str, Any]) -> Any:
    user_id = _context_lookup(context, 'user_id', 'userId', 'uid', 'sub', 'id', 'user', 'principal')
    if user_id is None and isinstance(context, dict):
        user_id = _get(context, 'user_id', 'userId', 'uid', 'sub', 'id', 'user')
    if user_id is None:
        user_id = _get(data, 'user_id', 'userId', 'uid', 'sub', 'user')
    if isinstance(user_id, dict):
        return _get(user_id, 'id', 'user_id', 'userId', 'uid', 'sub')
    return user_id


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
