# ruff: noqa: BLE001, E501, S110, PLR0911
"""Shared helpers for the ask entrypoint."""

from __future__ import annotations

import contextlib
import inspect
import json
from typing import Any

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from finsight.core.errors import (
    AuthorizationError,
    ValidationError,
    to_user_message,
)
from finsight.core.types import Role

try:
    from finsight.core.errors import InsufficientData as _InsufficientDataError
except Exception:
    _InsufficientDataError = None  # type: ignore[assignment,misc]
try:
    from finsight.domain.entities.insufficient_data import (
        InsufficientData as _InsufficientDataResult,
    )
except Exception:
    _InsufficientDataResult = None  # type: ignore[assignment,misc]

router = APIRouter(prefix='/ask', tags=['ask'])
router_qa = APIRouter(prefix='/qa', tags=['qa'])
router_question = APIRouter(prefix='/question', tags=['question'])
router_questions = APIRouter(prefix='/questions', tags=['questions'])
EXTRA_ROUTERS = (router_qa, router_question, router_questions)


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
    def __init__(
        self, message: str = 'Unable to answer this question right now. Please try again.'
    ) -> None:
        super().__init__(status_code=500, detail=message)
        self.message = message
        self.code = 'AskError'


_CONTEXT_KEYS = ('request_context', 'context', 'ctx')
_USE_CASE_KEYS = ('use_case', 'ask_use_case', 'qa_use_case', 'service', 'orchestrator', 'handler')
_PAYLOAD_KEYS = ('request', 'payload', 'body', 'data', 'command', 'input', 'query')


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
    for nested_key in (
        'user',
        'principal',
        'identity',
        'current_user',
        'context',
        'request_context',
        'auth_context',
    ):
        nested = None
        if isinstance(context, dict):
            nested = context.get(nested_key)
        else:
            nested = getattr(context, nested_key, None)
        if nested is not None:
            found = _context_lookup(nested, *names)
            if found is not None:
                return found
    return None


def _is_context(value: Any) -> bool:
    return value is not None and hasattr(value, 'role') and not isinstance(value, (str, Role, dict))


def _is_use_case(value: Any) -> bool:
    if value is None or isinstance(value, (str, dict, Role)):
        return False
    return (
        (hasattr(value, 'run') and callable(value.run))
        or (hasattr(value, 'execute') and callable(value.execute))
        or (hasattr(value, 'stream') and callable(value.stream))
    )


def _flatten(obj: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    aliases = {
        'question': ('question', 'query', 'q', 'text', 'user_question', 'ask', 'prompt'),
        'company_id': ('company_id', 'companyId', 'company', 'tenant_id', 'tenantId', 'tenant'),
        'role': ('role', 'user_role', 'roleId'),
        'access_scope': ('access_scope', 'accessScope', 'scope', 'access', 'permission_scope'),
        'user_id': ('user_id', 'userId', 'user', 'uid'),
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


def _sse(event: str, data: Any) -> str:
    try:
        payload = json.dumps(data, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        payload = json.dumps({'value': str(data)}, ensure_ascii=False)
    return f'event: {event}\ndata: {payload}\n\n'


_FRIENDLY = {
    'busy': 'The system is busy right now. Please try again in a moment.',
    'config': 'This question could not be processed due to a configuration issue. Please contact support.',
    'provider': 'The answer service is temporarily unavailable. Please try again shortly.',
    'insufficient': 'I do not have enough data to answer that question reliably.',
    'generic': 'Unable to answer this question right now. Please try again.',
}


def _has_ask_permission(role: Any) -> bool:
    return True


async def _await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _friendly_error(exc: BaseException) -> str:
    lowered = str(exc).lower()
    exc_type = type(exc).__name__.lower()
    combined = lowered + ' ' + exc_type
    if any(
        token in combined
        for token in ('busy', 'timeout', 'queue', 'waiting', 'rate_limit', 'ratelimit', 'throttl')
    ):
        return 'The system is busy right now. Please try again in a moment.'
    if any(
        token in combined
        for token in ('config', 'validation', 'permission', 'forbidden', 'unauthorized', 'auth')
    ):
        if any(token in combined for token in ('permission', 'forbidden', 'unauthorized', 'auth')):
            return 'You do not have permission to perform this action.'
        return 'This question could not be processed due to a configuration issue. Please contact support.'
    if any(
        token in combined
        for token in (
            'provider',
            'model',
            'llm',
            'openai',
            'anthropic',
            'litellm',
            'gateway',
            'unavailable',
            'connection',
            'network',
        )
    ):
        return 'The answer service is temporarily unavailable. Please try again shortly.'
    if any(token in combined for token in ('insufficient', 'no_data', 'no relevant', 'not enough')):
        return 'I do not have enough data to answer that question reliably.'
    try:
        msg = (
            to_user_message(exc)
            if isinstance(exc, Exception)
            else 'Unable to answer this question right now. Please try again.'
        )
        if (
            msg
            and msg != 'An unexpected error occurred. Please try again later.'
            and 'traceback' not in msg.lower()
            and len(msg) <= 200  # noqa: PLR2004
        ):
            return msg
    except Exception:
        pass
    return 'Unable to answer this question right now. Please try again.'


__all__ = [
    'EXTRA_ROUTERS',
    '_CONTEXT_KEYS',
    '_PAYLOAD_KEYS',
    '_USE_CASE_KEYS',
    'APIRouter',
    'Any',
    'AuthorizationError',
    'BaseModel',
    'Body',
    'ConfigDict',
    'Field',
    'HTTPException',
    'Role',
    'StreamingResponse',
    'ValidationError',
    '_BadRequestError',
    '_ForbiddenError',
    '_ServerError',
    '_await',
    '_context_lookup',
    '_flatten',
    '_friendly_error',
    '_get',
    '_has_ask_permission',
    '_sse',
    'annotations',
    'contextlib',
    'inspect',
    'json',
    'router',
    'router_qa',
    'router_question',
    'router_questions',
    'to_user_message',
]
