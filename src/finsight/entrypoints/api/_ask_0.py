# ruff: noqa: BLE001, E501, I001, ANN401
"""API entrypoint for Q&A ask functionality with typed SSE streaming."""

from __future__ import annotations
import contextlib
import inspect
import json
from typing import Any
from typing import Any as _Any
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
_get_ask_use_case: _Any = None
try:
    from finsight.composition.ask_question import (
        get_ask_use_case as _get_ask_use_case_raw,
    )

    def _get_ask_use_case(*args: Any, **kwargs: Any) -> Any:
        if args or kwargs:
            return _get_ask_use_case_raw(*args, **kwargs)
        try:
            return _get_ask_use_case_raw()
        except TypeError:
            return _get_ask_use_case_raw(None)
except ImportError:  # pragma: no cover - composition may not expose ask yet
    _get_ask_use_case = None
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
_USE_CASE_KEYS = (
    'use_case',
    'ask_use_case',
    'qa_use_case',
    'service',
    'orchestrator',
    'handler',
    'ask',
    'handler_service',
    'container',
    'composition',
    'app',
    'factory',
)
_PAYLOAD_KEYS = (
    'request',
    'payload',
    'body',
    'data',
    'command',
    'input',
    'question_input',
    'query',
)
_REPOSITORY_KEYS = ('repository', 'repo')
_EVENT_ALIASES = {
    'status': 'status',
    'progress': 'status',
    'state': 'status',
    'info': 'status',
    'delta': 'delta',
    'token': 'delta',
    'answer_delta': 'delta',
    'chunk': 'delta',
    'text': 'delta',
    'content': 'delta',
    'citation': 'citation',
    'source': 'citation',
    'reference': 'citation',
    'insufficient_data': 'insufficient_data',
    'insufficient': 'insufficient_data',
    'no_answer': 'insufficient_data',
    'complete': 'complete',
    'done': 'complete',
    'finished': 'complete',
    'end': 'complete',
    'completion': 'complete',
    'error': 'error',
    'failure': 'error',
    'failed': 'error',
    'busy': 'busy',
}
_FRIENDLY = {
    'busy': 'The system is busy right now. Please try again in a moment.',
    'config': 'This question could not be processed due to a configuration issue. Please contact support.',
    'provider': 'The answer service is temporarily unavailable. Please try again shortly.',
    'insufficient': 'I do not have enough data to answer that question reliably.',
    'generic': 'Unable to answer this question right now. Please try again.',
}


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
    """Best-effort extraction of a named attribute from a context object or dict."""
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
    return value is not None and (
        hasattr(value, 'role') and not isinstance(value, (str, Role, dict))
    )


def _is_use_case(value: Any) -> bool:
    if value is None or isinstance(value, (str, dict, Role)):
        return False
    if (
        callable(value)
        and not hasattr(value, 'execute')
        and not hasattr(value, 'run')
        and not hasattr(value, 'ask')
        and not hasattr(value, 'stream')
    ):
        # Factories resolved later.
        return False
    for attr in ('execute', 'run', 'ask', 'answer', 'handle', 'stream', 'stream_ask', 'ask_stream'):
        if hasattr(value, attr) and callable(getattr(value, attr, None)):
            return True
    return callable(value) and not _is_context(value)


def _flatten(obj: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    aliases = {
        'question': ('question', 'query', 'q', 'text', 'user_question', 'ask', 'prompt'),
        'company_id': ('company_id', 'companyId', 'company', 'tenant_id', 'tenantId', 'tenant'),
        'role': ('role', 'user_role', 'roleId'),
        'access_scope': ('access_scope', 'accessScope', 'scope', 'access', 'permission_scope'),
        'user_id': ('user_id', 'userId', 'user', 'uid'),
        'session_id': ('session_id', 'sessionId', 'session'),
        'cache': ('cache', 'answer_cache', 'cache_enabled'),
        'stream': ('stream', 'streaming', 'sse'),
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


async def _await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


__all__ = [
    'EXTRA_ROUTERS',
    '_CONTEXT_KEYS',
    '_EVENT_ALIASES',
    '_FRIENDLY',
    '_PAYLOAD_KEYS',
    '_REPOSITORY_KEYS',
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
    '_Any',
    '_BadRequestError',
    '_ForbiddenError',
    '_ServerError',
    '_await',
    '_context_lookup',
    '_flatten',
    '_get',
    '_get_ask_use_case',
    '_is_context',
    '_is_use_case',
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
