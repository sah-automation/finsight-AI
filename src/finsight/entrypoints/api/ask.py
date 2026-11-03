# ruff: noqa: BLE001, PLC0415, PLR0911, PLR0912, PLR0915, PLR2004, S110, I001, F403, F405, E402, F811
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


# ruff: noqa: BLE001, PLR0912
"""Request normalization helpers for the ask entrypoint."""


from typing import Any


try:
    from finsight.core.types import CompanyId as _CompanyId
    from finsight.core.types import RequestContext as _RequestContext
    from finsight.core.types import Role as _Role
    from finsight.core.types import TraceId as _TraceId
    from finsight.core.types import UserId as _UserId
except Exception:  # pragma: no cover
    _CompanyId = None  # type: ignore[misc,assignment]
    _RequestContext = None  # type: ignore[misc,assignment]
    _Role = None  # type: ignore[misc,assignment]
    _TraceId = None  # type: ignore[misc,assignment]
    _UserId = None  # type: ignore[misc,assignment]


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

    # lift context/use_case
    for key in ('request_context', 'context', 'ctx'):
        if key in data and context is None:
            context = data.pop(key)
    for key in ('use_case', 'ask_use_case', 'qa_use_case'):
        if key in data and use_case is None:
            use_case = data.pop(key)

    # Propagate scoping fields if needed.
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


__all__ = ['_build_frozen_request_context', '_resolve_context_and_data']


# ruff: noqa: PLR0912, PLR0915
"""Outcome to event normalization helpers for the ask entrypoint."""


from typing import Any


def _events_from_outcome(outcome: Any, data: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
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
            # Continue to normal delta emission below by clearing marker? Keep simple.
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
    # InsufficientDataResult check by name.
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

    complete_payload: dict[str, Any] = {'done': True}
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


__all__ = ['_events_from_outcome']


"""Call helpers for the ask use case."""


import inspect
from typing import Any


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


__all__ = ['_call_stream', '_invoke']


# ruff: noqa: BLE001, S110, PLR0911, PLR0912, PLR0915
"""Request handling for the ask entrypoint."""


import inspect
from typing import Any

from fastapi import Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from finsight.core.errors import (
    AuthorizationError,
    ValidationError,
    to_user_message,
)
from finsight.core.errors import InsufficientData as _InsufficientDataError
from finsight.domain.entities.insufficient_data import InsufficientData as _InsufficientDataResult


try:
    from finsight.composition.providers import get_ask_use_case as _get_ask_use_case_raw
except Exception:
    _get_ask_use_case_raw = None  # type: ignore[assignment]


async def _resolve_use_case(candidate: Any, data: dict[str, Any], context: Any) -> Any:
    if candidate is not None:
        if inspect.isawaitable(candidate):
            candidate = await candidate
        if isinstance(candidate, dict):
            for key in ('ask_use_case', 'use_case', 'service', 'orchestrator', 'handler'):
                if key in candidate:
                    candidate = candidate[key]
                    break
        return candidate
    try:
        if _get_ask_use_case_raw is not None:
            resolved = _get_ask_use_case_raw()
            if inspect.isawaitable(resolved):
                resolved = await resolved
            if resolved is not None:
                return resolved
    except Exception:
        pass
    raise RuntimeError('ask use case is not available')


async def _handle(*args: Any, **kwargs: Any) -> StreamingResponse:
    context, data, use_case_candidate = await _resolve_context_and_data(*args, **kwargs)

    async def _generator() -> Any:
        emitted_complete = False
        try:
            role_candidate = None
            if context is not None:
                role_candidate = _context_lookup(context, 'role', 'user_role', 'role_id', 'roleId')
            if role_candidate is None:
                role_candidate = data.get('role')

            if not _has_ask_permission(role_candidate):
                yield _sse(
                    'error',
                    {
                        'message': 'You do not have permission to perform this action.',
                        'code': 'AuthorizationError',
                    },
                )
                yield _sse('complete', {'done': True, 'error': True})
                return

            company_id = data.get('company_id')
            if company_id is None and context is not None:
                company_id = _context_lookup(context, 'company_id', 'companyId', 'company')
            if company_id is not None:
                data['company_id'] = company_id
            else:
                yield _sse(
                    'error', {'message': 'company_id is required.', 'code': 'ValidationError'}
                )
                yield _sse('complete', {'done': True, 'error': True})
                return

            question = data.get('question') or data.get('query')
            if not question:
                question = data.get('_raw')
                if question is not None:
                    question = str(question)
                    data['question'] = question

            frozen_context = _build_frozen_request_context(data, context)

            yield _sse('status', {'status': 'received', 'question': question})

            use_case = await _resolve_use_case(use_case_candidate, data, context)

            stream_obj = await _call_stream(use_case, data, context, frozen_context=frozen_context)
            agen = None
            if stream_obj is not None:
                if hasattr(stream_obj, '__aiter__'):
                    agen = stream_obj
                elif hasattr(stream_obj, '__iter__') and not isinstance(stream_obj, (str, dict)):

                    async def _agen() -> Any:
                        for item in stream_obj:
                            yield item

                    agen = _agen()
            if agen is not None:
                yield _sse('status', {'status': 'answering'})
                async for raw in agen:
                    for etype, payload in _events_from_outcome(raw, data):
                        if etype == 'complete':
                            emitted_complete = True
                        yield _sse(etype, payload)
                if not emitted_complete:
                    yield _sse('complete', {'done': True})
                return

            ctx_arg = frozen_context if frozen_context is not None else context
            outcome = await _invoke(use_case, ctx_arg, data.get('question'))
            for etype, payload in _events_from_outcome(outcome, data):
                if etype == 'complete':
                    emitted_complete = True
                yield _sse(etype, payload)

            if not emitted_complete:
                yield _sse('complete', {'done': True})
        except Exception as exc:
            # Friendly handling.
            if _InsufficientDataResult is not None and isinstance(exc, _InsufficientDataResult):
                reason = getattr(exc, 'reason', None) or _friendly_error(exc)
                yield _sse(
                    'insufficient_data', {'reason': reason, 'question': data.get('question')}
                )
                yield _sse('complete', {'done': True, 'insufficient_data': True})
                return
            if isinstance(exc, ValidationError):
                msg = getattr(exc, 'message', None) or to_user_message(exc) or _FRIENDLY['config']
                yield _sse('error', {'message': msg, 'code': 'ValidationError'})
                yield _sse('complete', {'done': True, 'error': True})
                return
            if isinstance(exc, AuthorizationError):
                msg = (
                    getattr(exc, 'message', None)
                    or to_user_message(exc)
                    or 'You do not have permission to perform this action.'
                )
                yield _sse('error', {'message': msg, 'code': 'AuthorizationError'})
                yield _sse('complete', {'done': True, 'error': True})
                return
            if _InsufficientDataError is not None and isinstance(exc, _InsufficientDataError):
                reason = getattr(exc, 'reason', None) or _friendly_error(exc)
                yield _sse(
                    'insufficient_data', {'reason': reason, 'question': data.get('question')}
                )
                yield _sse('complete', {'done': True, 'insufficient_data': True})
                return
            msg = _friendly_error(exc)
            lowered = (str(exc) + ' ' + type(exc).__name__).lower()
            if any(t in lowered for t in ('busy', 'timeout', 'queue', 'waiting', 'rate')):
                code = 'BusyError'
            elif any(t in lowered for t in ('config', 'validation')):
                code = 'ConfigurationError'
            elif any(
                t in lowered
                for t in (
                    'provider',
                    'model',
                    'llm',
                    'gateway',
                    'connection',
                    'network',
                    'unavailable',
                )
            ):
                code = 'ProviderError'
            else:
                code = 'AskError'
            yield _sse('error', {'message': msg, 'code': code})
            yield _sse('complete', {'done': True, 'error': True})

    return StreamingResponse(
        _generator(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )


def _normalize_event(raw: Any) -> tuple[str, dict[str, Any]]:
    # Import from _ask_0? Not defined there. Minimal normalize returning str?
    # We need events; since stream returns raw span? Usually stream yields Answer object directly.
    if isinstance(raw, (tuple, list)) and len(raw) >= 1:
        etype = str(raw[0])
        payload = raw[1] if len(raw) > 1 else {}
        etype = str(etype)
        if not isinstance(payload, dict):
            payload = {'value': payload}
        return etype, payload
    if isinstance(raw, dict):
        return 'delta', raw
    return 'delta', {'value': str(raw)}


class _AskQuestionRequest(BaseModel):
    model_config = ConfigDict(title='AskQuestionRequest')

    question: str | None = None
    query: str | None = None
    q: str | None = None
    company_id: str | None = None
    companyId: str | None = None  # noqa: N815
    thread_id: str | None = None
    threadId: str | None = None  # noqa: N815
    access_scope: Any = None
    context: Any = None
    use_case: Any = None


AskQuestionRequest = _AskQuestionRequest


class _AskQuestionEvent(BaseModel):
    model_config = ConfigDict(title='AskQuestionEvent')

    event: str = Field(..., description='SSE event name.')
    data: dict[str, Any] = Field(default_factory=dict, description='Event payload.')


AskQuestionEvent = _AskQuestionEvent


async def _http_ask(
    payload: _AskQuestionRequest | None = Body(default=None), context: Any = None
) -> StreamingResponse:
    data = (
        payload.model_dump(exclude_none=True)
        if isinstance(payload, _AskQuestionRequest)
        else payload
    )
    return await _handle(data, context=context)


__all__ = [
    'AskQuestionEvent',
    'AskQuestionRequest',
    '_AskQuestionEvent',
    '_AskQuestionRequest',
    '_handle',
    '_http_ask',
]


class Ask:
    """Thin wrapper exposing the ask entrypoint as a callable object."""

    def __init__(self, context: Any = None) -> None:
        from finsight.composition.providers import get_ask_use_case

        self.use_case = get_ask_use_case()
        self.context = context

    async def run(self, *args: Any, **kwargs: Any) -> StreamingResponse:
        if self.use_case is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('use_case', self.use_case)
        if self.context is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('context', self.context)
        return await _handle(*args, **kwargs)

    __call__ = run


for _r in (router, router_qa, router_question, router_questions):

    @_r.get('/health')
    async def _health() -> dict[str, str]:
        return {'status': 'ok'}

    _responses: dict[int, dict[str, Any]] | None = {
        200: {
            'description': 'Server-sent event stream of typed question events.',
            'content': {
                'text/event-stream': {'schema': {'$ref': '#/components/schemas/AskQuestionEvent'}}
            },
        }
    }

    @_r.post('', response_model=None, responses=_responses)  # type: ignore[arg-type]
    async def _post(
        payload: _AskQuestionRequest | None = Body(default=None), context: Any = None
    ) -> StreamingResponse:
        data = (
            payload.model_dump(exclude_none=True)
            if isinstance(payload, _AskQuestionRequest)
            else payload
        )
        return await _handle(data, context=context)

    @_r.post('/', response_model=None, responses=_responses)  # type: ignore[arg-type]
    async def _post_slash(
        payload: _AskQuestionRequest | None = Body(default=None), context: Any = None
    ) -> StreamingResponse:
        data = (
            payload.model_dump(exclude_none=True)
            if isinstance(payload, _AskQuestionRequest)
            else payload
        )
        return await _handle(data, context=context)


ask = _handle

qa = _handle

answer = _handle

ask_question = _handle

stream = _handle

stream_ask = _handle

ask_endpoint = _handle

qa_endpoint = _handle

handle_ask = _handle

run_ask = _handle


__all__ = [
    'EXTRA_ROUTERS',
    'Ask',
    'answer',
    'ask',
    'ask_endpoint',
    'ask_question',
    'handle_ask',
    'qa',
    'qa_endpoint',
    'router',
    'router_qa',
    'router_question',
    'router_questions',
    'run_ask',
    'stream',
    'stream_ask',
]
