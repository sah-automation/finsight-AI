# ruff: noqa: PLR0911, I001
"""API entrypoint for feedback and report-wrong-source submissions (Slice 7.3)."""

from __future__ import annotations
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
    def __init__(self, message: str = 'Feedback request failed. Please try again later.') -> None:
        super().__init__(status_code=500, detail=message)
        self.message = message
        self.code = 'FeedbackError'


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


def _flatten(obj: Any) -> dict[str, Any]:
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
