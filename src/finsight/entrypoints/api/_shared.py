# ruff: noqa: BLE001, PLR0911, PLR0912, PLR0915, PLR2004, S110, E501
"""Shared helpers for the entrypoint API routers."""

from __future__ import annotations

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
from finsight.core.types import (
    CompanyId as _CompanyId,
)
from finsight.core.types import (
    RequestContext as _RequestContext,
)
from finsight.core.types import (
    Role,
)
from finsight.core.types import (
    Role as _Role,
)
from finsight.core.types import (
    TraceId as _TraceId,
)
from finsight.core.types import (
    UserId as _UserId,
)


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


class _NotFoundError(HTTPException):
    def __init__(self, message: str = 'Resource not found.') -> None:
        super().__init__(status_code=404, detail=message)
        self.message = message
        self.code = 'NotFound'


class _ServerError(HTTPException):
    def __init__(self, message: str = 'Request failed. Please try again later.') -> None:
        super().__init__(status_code=500, detail=message)
        self.message = message
        self.code = 'ServerError'


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict):
            if name in obj and obj.get(name) is not None:
                return obj.get(name)
        elif obj is not None and hasattr(obj, name):
            value = getattr(obj, name, None)
            if value is not None:
                return value
    return default


def _first(value: Any, default: Any = None) -> Any:
    if isinstance(value, (list, tuple)) and value:
        return value[0]
    return value if value is not None else default


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
        'user_context',
        'security_context',
    )
    for nested_key in nested_keys:
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
    if value is None:
        return False
    if isinstance(value, dict):
        # Request/payload wrappers are not pure contexts, even when they also
        # carry scoping fields such as company_id. An explicit context key
        # always wins (context wrappers may nest payload-ish identifiers).
        _core_payload_keys = (
            set(_PAYLOAD_KEYS)
            | set(_USE_CASE_KEYS)
            | {
                'question',
                'query',
                'q',
                'text',
                'action',
                'rating',
            }
        )
        if any(key in value for key in _core_payload_keys) and not any(
            key in value for key in _CONTEXT_KEYS
        ):
            return False
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
        return any(key in value for key in ('company_id', 'companyId', 'role', 'user_id', 'userId'))
    # object-style context
    if hasattr(value, 'role') and not isinstance(value, (str, Role, dict)):
        return True
    return any(
        hasattr(value, attr) for attr in ('role', 'company_id', 'companyId', 'user_id', 'userId')
    )


def _is_use_case(value: Any) -> bool:
    if value is None or isinstance(value, (str, dict, Role)):
        return False
    return (
        (hasattr(value, 'run') and callable(value.run))
        or (hasattr(value, 'execute') and callable(value.execute))
        or (hasattr(value, 'stream') and callable(value.stream))
        or (hasattr(value, 'upload') and callable(value.upload))
        or (hasattr(value, 'onboard') and callable(value.onboard))
    )


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
_PAYLOAD_KEYS = ('request', 'payload', 'body', 'data', 'command', 'input', 'query')
_USE_CASE_KEYS = ('use_case', 'ask_use_case', 'qa_use_case', 'service', 'orchestrator', 'handler')


def _flatten(obj: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    aliases = {
        'question': ('question', 'query', 'q', 'text', 'user_question', 'ask', 'prompt'),
        'company_id': ('company_id', 'companyId', 'company', 'tenant_id', 'tenantId', 'tenant'),
        'role': ('role', 'user_role', 'roleId'),
        'access_scope': ('access_scope', 'accessScope', 'scope', 'access', 'permission_scope'),
        'user_id': ('user_id', 'userId', 'user', 'uid'),
        'thread_id': ('thread_id', 'threadId', 'thread', 'chat_id', 'conversation_id', 'id'),
        'feedback_id': ('feedback_id', 'feedbackId', 'id'),
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
            and len(msg) <= 200
        ):
            return msg
    except Exception:
        pass
    return 'Unable to answer this question right now. Please try again.'


def _build_frozen_request_context(data: dict[str, Any], context: Any) -> Any:
    if _RequestContext is None:
        return context
    try:
        company_id = data.get('company_id')
        if company_id is None and context is not None:
            company_id = _context_lookup(context, 'company_id', 'companyId', 'company')
        if company_id is None:
            return context

        role = data.get('role')
        if role is None and context is not None:
            role = _context_lookup(context, 'role', 'user_role', 'roleId')
        if role is None:
            role = getattr(context, 'role', None) if context is not None else None
        if role is None:
            role = _Role.EXECUTIVE_LEADERSHIP
        if isinstance(role, str):
            try:
                role = _Role(role)
            except Exception:
                role = _Role.EXECUTIVE_LEADERSHIP

        user_id = data.get('user_id')
        if user_id is None and context is not None:
            user_id = _context_lookup(context, 'user_id', 'userId', 'user', 'uid')
        if user_id is None and context is not None:
            user_id = getattr(context, 'user_id', None)
        if user_id is None:
            user_id = 'unknown'

        trace_id = None
        if context is not None:
            trace_id = _context_lookup(context, 'trace_id', 'traceId', 'trace')
        if trace_id is None:
            trace_id = 'trace'

        permissions: dict[Any, Any] = {}
        if context is not None:
            perms = _context_lookup(context, 'permissions')
            if isinstance(perms, dict):
                permissions = perms

        access_scope = data.get('access_scope')
        if access_scope is None and context is not None:
            access_scope = _context_lookup(context, 'access_scope', 'accessScope', 'scope')
        scopes: list[Any]
        if isinstance(access_scope, list):
            scopes = access_scope
        elif access_scope is None:
            scopes = []
        else:
            scopes = [access_scope]

        return _RequestContext(
            company_id=_CompanyId(str(company_id)),
            user_id=_UserId(str(user_id)),
            role=role,
            trace_id=_TraceId(str(trace_id)),
            permissions=permissions,
            access_scope=scopes,
        )
    except Exception:
        return context


async def _resolve_context_and_data(*args: Any, **kwargs: Any) -> tuple[Any, dict[str, Any], Any]:
    context = kwargs.get('context')
    data: dict[str, Any] = {}
    use_case = kwargs.get('use_case')

    if 'data' in kwargs and isinstance(kwargs.get('data'), dict):
        data.update(kwargs['data'])
    for key, value in kwargs.items():
        if key in {'context', 'use_case'}:
            continue
        if isinstance(value, dict):
            data.update(value)
        else:
            flat = _flatten(value)
            if flat:
                data.update(flat)
            else:
                data[key] = value
    for value in args:
        if _is_context(value):
            context = context or value
        elif _is_use_case(value):
            use_case = use_case or value
        elif isinstance(value, dict):
            data.update(value)
        else:
            flattened = _flatten(value)
            if flattened:
                data.update(flattened)

    for key in ('request_context', 'context', 'ctx'):
        if key in data and context is None:
            context = data.pop(key)
    for key in ('use_case', 'ask_use_case', 'qa_use_case'):
        if key in data and use_case is None:
            use_case = data.pop(key)

    if context is not None:
        company = _context_lookup(context, 'company_id', 'companyId', 'company')
        if company is not None and 'company_id' not in data:
            data['company_id'] = company
        role = _context_lookup(context, 'role', 'user_role', 'roleId')
        if role is not None and 'role' not in data:
            data['role'] = role
        scope = _context_lookup(context, 'access_scope', 'accessScope', 'scope')
        if scope is not None and 'access_scope' not in data:
            data['access_scope'] = scope
        user = _context_lookup(context, 'user_id', 'userId', 'user', 'uid')
        if user is not None and 'user_id' not in data:
            data['user_id'] = user

    return context, data, use_case


def _events_from_outcome(outcome: Any, data: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    # Copied from ask router; behavior preserved.
    events: list[tuple[str, dict[str, Any]]] = []
    is_insufficient = False
    reason = 'insufficient data'
    class_name = type(outcome).__name__.lower()
    if (
        getattr(outcome, 'unavailable', False)
        if not isinstance(outcome, dict)
        else outcome.get('unavailable', False)
    ):
        text = (
            outcome.get('message')
            if isinstance(outcome, dict)
            else getattr(outcome, 'message', None)
        )
        events.append(('status', {'status': 'answering'}))
        if text:
            pass
    if isinstance(outcome, dict) and (
        outcome.get('insufficient_data') or outcome.get('insufficient')
    ):
        is_insufficient = True
        reason = outcome.get('reason') or outcome.get('message') or reason
    elif getattr(outcome, 'insufficient_data', False):
        is_insufficient = True
        reason = getattr(outcome, 'reason', reason) or reason
    elif isinstance(outcome, Exception):
        if 'insufficient' in class_name or 'insufficient' in str(outcome).lower():
            is_insufficient = True
            reason = str(outcome) or reason
    if (
        type(outcome).__name__ in ('InsufficientData',)
        or (
            getattr(outcome, 'insufficient_data', False) is True
            and not getattr(outcome, 'answer', None)
        )
    ) and (not isinstance(outcome, dict) or outcome.get('insufficient_data')):
        is_insufficient = True
        reason = getattr(outcome, 'reason', reason) or reason

    if is_insufficient:
        events.append(('status', {'status': 'checking_evidence'}))
        events.append(('insufficient_data', {'reason': reason, 'question': data.get('question')}))
        events.append(('complete', {'done': True, 'insufficient_data': True}))
        return events

    answer_text = None
    citations: list[Any] = []
    model_name = None
    cached = None

    if isinstance(outcome, dict):
        for key in ('answer', 'text', 'response', 'output', 'result', 'message'):
            if outcome.get(key) is not None:
                candidate_val = outcome.get(key)
                if isinstance(candidate_val, str):
                    answer_text = candidate_val
                    break
                if isinstance(candidate_val, dict) and candidate_val.get('text') is not None:
                    answer_text = str(candidate_val.get('text'))
                    break
        citations = (
            outcome.get('citations') or outcome.get('sources') or outcome.get('references') or []
        )
        model_name = outcome.get('model') or outcome.get('model_name') or outcome.get('model_id')
        cached = outcome.get('cached') or outcome.get('cache_hit')
    elif isinstance(outcome, str):
        answer_text = outcome
    else:
        for attr in ('answer', 'text', 'response', 'output', 'content', 'result'):
            val = getattr(outcome, attr, None)
            if isinstance(val, str):
                answer_text = val
                break
        citations = (
            getattr(outcome, 'citations', None)
            or getattr(outcome, 'sources', None)
            or getattr(outcome, 'references', None)
            or []
        )
        model_name = (
            getattr(outcome, 'model', None)
            or getattr(outcome, 'model_name', None)
            or getattr(outcome, 'model_id', None)
        )
        cached = getattr(outcome, 'cached', None) or getattr(outcome, 'cache_hit', None)

    if citations is None:
        citations = []

    events.append(('status', {'status': 'answering'}))

    if answer_text is not None:
        events.append(('delta', {'delta': answer_text, 'text': answer_text}))

    for cit in citations:
        if isinstance(cit, dict):
            events.append(('citation', {'citation': cit}))
        else:
            payload: dict[str, Any] = {}
            for name in (
                'document',
                'document_id',
                'document_name',
                'document_title',
                'title',
                'document_version',
                'version',
                'page',
                'page_number',
                'table',
                'table_id',
                'section',
                'chunk_id',
                'chunk',
                'score',
                'snippet',
                'start_char',
                'end_char',
                'char_start',
                'char_end',
                'citation_locator',
                'locator',
                'citation_id',
                'citation_token',
                'citation_locator_token',
                'signed_locator',
                'signed_citation_locator',
                'token',
                'locator_token',
                'citation_locator_id',
            ):
                val = getattr(cit, name, None)
                if val is not None:
                    payload[name] = val
            if not payload:
                payload = {'value': str(cit)}
            events.append(('citation', {'citation': payload}))

    complete_payload: dict[Any, Any] = {'done': True}
    if model_name is not None:
        complete_payload['model'] = model_name
    if cached is not None:
        complete_payload['cached'] = bool(cached)
    if answer_text is None and not citations:
        complete_payload['insufficient_data'] = True

    thread_id = None
    answer_id = None
    if isinstance(outcome, dict):
        thread_id = _get(outcome, 'thread_id', 'threadId', 'thread', 'chat_id', 'conversation_id')
        answer_id = _get(outcome, 'answer_id', 'answerId', 'answer', 'response_id', 'id')
        nested_thread = outcome.get('thread')
        if isinstance(nested_thread, dict):
            thread_id = thread_id or _get(nested_thread, 'thread_id', 'threadId', 'id', 'thread')
        nested_answer = outcome.get('answer')
        if isinstance(nested_answer, dict):
            answer_id = answer_id or _get(nested_answer, 'answer_id', 'answerId', 'id')
    else:
        thread_id = _get(outcome, 'thread_id', 'threadId', 'thread', 'chat_id', 'conversation_id')
        answer_id = _get(outcome, 'answer_id', 'answerId', 'answer', 'response_id', 'result_id')
        nested_thread = getattr(outcome, 'thread', None)
        if isinstance(nested_thread, dict):
            thread_id = thread_id or _get(nested_thread, 'thread_id', 'threadId', 'id', 'thread')
        nested_answer = getattr(outcome, 'answer', None)
        if isinstance(nested_answer, dict):
            answer_id = answer_id or _get(nested_answer, 'answer_id', 'answerId', 'id')
    if isinstance(answer_id, str) and answer_id == answer_text:
        answer_id = _get(outcome, 'answer_id', 'answerId', 'response_id', 'result_id')
    if thread_id is not None:
        complete_payload['thread_id'] = thread_id
        complete_payload['threadId'] = thread_id
    if answer_id is not None:
        complete_payload['answer_id'] = answer_id
        complete_payload['answerId'] = answer_id
    events.append(('complete', complete_payload))
    return events


async def _call_stream(
    use_case: Any, data: dict[str, Any], context: Any, frozen_context: Any = None
) -> Any:
    stream_method = getattr(use_case, 'stream', None)
    if not callable(stream_method):
        return None
    question = data.get('question')
    ctx = frozen_context if frozen_context is not None else context
    try:
        result = stream_method(ctx, question)
        if inspect.isawaitable(result):
            result = await result
    except TypeError:
        try:
            result = stream_method(request_context=ctx, question=question)
            if inspect.isawaitable(result):
                result = await result
        except TypeError:
            return None
    return result


async def _invoke(use_case: Any, context: Any, question: Any) -> Any:
    run_method = getattr(use_case, 'run', None)
    if not callable(run_method):
        raise RuntimeError('ask use case is not callable')  # noqa: TRY004
    result = run_method(context, question)
    if inspect.isawaitable(result):
        result = await result
    return result


__all__ = [
    'APIRouter',
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
    '_NotFoundError',
    '_ServerError',
    '_await',
    '_build_frozen_request_context',
    '_call_stream',
    '_context_lookup',
    '_events_from_outcome',
    '_first',
    '_flatten',
    '_friendly_error',
    '_get',
    '_has_ask_permission',
    '_invoke',
    '_is_context',
    '_is_use_case',
    '_resolve_context_and_data',
    '_sse',
]


class _PartitionMissingError(HTTPException):
    def __init__(self, message: str = 'Partition missing.') -> None:
        super().__init__(status_code=404, detail=message)
        self.message = message
        self.code = 'PartitionMissing'


def _extract_company_id(context: Any, data: dict[str, Any]) -> Any:
    value = _context_lookup(
        context, 'company_id', 'companyId', 'company', 'tenant_id', 'tenantId', 'tenant'
    )
    if value is None:
        value = _get(data, 'company_id', 'companyId', 'company', 'tenant_id', 'tenantId', 'tenant')
    return value


def _extract_user_id(context: Any, data: dict[str, Any]) -> Any:
    value = _context_lookup(context, 'user_id', 'userId', 'user', 'uid', 'sub')
    if value is None:
        value = _get(data, 'user_id', 'userId', 'user', 'uid', 'sub')
    return value


def _try_context_role(context: Any) -> Any:
    return _context_lookup(context, 'role', 'user_role', 'roleId')


def _normalize_role(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return value.strip().lower()
    return str(value).strip().lower()


def _strip_empty(mapping: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in mapping.items() if v is not None and v not in ('', [], {})}
