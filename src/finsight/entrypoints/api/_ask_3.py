# ruff: noqa: BLE001, PLR0912, PLR0915, TRY300, I001, F403, F405
from __future__ import annotations
import inspect
from typing import Any

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
from ._ask_0 import *
from ._ask_1 import *
from ._ask_2 import *

try:
    from finsight.core.types import CompanyId as _CompanyId
    from finsight.core.types import RequestContext as _RequestContext
    from finsight.core.types import TraceId as _TraceId
    from finsight.core.types import UserId as _UserId
except Exception:  # pragma: no cover
    _CompanyId = None  # type: ignore[assignment,misc]
    _RequestContext = None  # type: ignore[assignment,misc]
    _TraceId = None  # type: ignore[assignment,misc]
    _UserId = None  # type: ignore[assignment,misc]


def _events_from_outcome(outcome: Any, data: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []

    # InsufficientData dataclass / error.
    is_insufficient = False
    reason = 'insufficient data'
    if _InsufficientDataError is not None and isinstance(outcome, _InsufficientDataError):
        is_insufficient = True
        reason = getattr(outcome, 'reason', reason) or reason
    _si = _InsufficientDataResult
    if _si is not None and isinstance(outcome, _si):
        is_insufficient = True
        reason = getattr(outcome, 'reason', reason) or reason
    elif isinstance(outcome, Exception):
        if (
            'insufficient' in type(outcome).__name__.lower()
            or 'insufficient' in str(outcome).lower()
        ):
            is_insufficient = True
            reason = str(outcome) or reason
    elif isinstance(outcome, dict):
        if outcome.get('insufficient_data') or outcome.get('insufficient'):
            is_insufficient = True
            reason = outcome.get('reason') or outcome.get('message') or reason

    if is_insufficient:
        events.append(('status', {'status': 'checking_evidence'}))
        events.append(('insufficient_data', {'reason': reason, 'question': data.get('question')}))
        events.append(('complete', {'done': True, 'insufficient_data': True}))
        return events

    # Extract answer text.
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
            payload = {}
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

    thread_id: Any = None
    answer_id: Any = None
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
    # Avoid mislabeling the answer text as an id.
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
    """Return an async iterable of raw events from the use case if supported."""
    question = data.get('question')
    method = getattr(use_case, 'stream', None)
    if callable(method):
        call_args: tuple[Any, ...] = (
            (frozen_context, question) if frozen_context is not None else (data, context)
        )
        try:
            result = method(*call_args)
            if inspect.isawaitable(result):
                result = await result
            return result
        except TypeError:
            try:
                result = method(
                    request_context=frozen_context if frozen_context is not None else context,
                    question=question,
                )
                if inspect.isawaitable(result):
                    result = await result
                return result
            except TypeError:
                pass
    return None


async def _collect_iterable(obj: Any) -> Any:
    if obj is None:
        return None
    if hasattr(obj, '__aiter__'):
        return obj
    if hasattr(obj, '__iter__') and not isinstance(obj, (str, dict)):
        # Convert sync iterable to async by yielding in a coroutine.
        async def _agen() -> Any:
            for item in obj:
                yield item

        return _agen()
    return None


def _wrap_sync_callable(use_case: Any, data: dict[str, Any]) -> Any:
    return None


__all__ = [
    '_build_frozen_request_context',
    '_call_stream',
    '_collect_iterable',
    '_events_from_outcome',
    '_wrap_sync_callable',
]


def _build_frozen_request_context(data: dict[str, Any], context: Any) -> Any:
    try:
        company_id = data.get('company_id')
        if company_id is None and context is not None:
            company_id = _context_lookup(context, 'company_id', 'companyId', 'company')
        if company_id is None:
            return context
        role = data.get('_role') or data.get('role')
        if role is None and context is not None:
            role = _context_lookup(context, 'role', 'user_role', 'roleId')
        if role is None:
            return context
        user_id = data.get('user_id')
        if user_id is None and context is not None:
            user_id = _context_lookup(context, 'user_id', 'userId', 'user', 'uid')
        access_scope = data.get('access_scope') or data.get('scope')
        if access_scope is None and context is not None:
            access_scope = _context_lookup(context, 'access_scope', 'accessScope', 'scope')
        if context is not None:
            trace_id = _context_lookup(context, 'trace_id', 'traceId', 'trace')
        else:
            trace_id = None
        permissions = {}
        if context is not None:
            perms = _context_lookup(context, 'permissions')
            if isinstance(perms, dict):
                permissions = perms
        if isinstance(access_scope, list):
            scopes = access_scope
        elif access_scope is None:
            scopes = []
        else:
            scopes = [access_scope]
        return _RequestContext(
            company_id=_CompanyId(str(company_id)),
            user_id=_UserId(str(user_id)) if user_id is not None else _UserId('unknown'),
            role=role,
            trace_id=_TraceId(str(trace_id)) if trace_id is not None else _TraceId('trace'),
            permissions=permissions,
            access_scope=scopes,
        )
    except Exception:
        return context
