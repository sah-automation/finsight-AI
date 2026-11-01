# ruff: noqa: BLE001, S110, PLR0911, PLR0912, PLR0915
"""Request handling for the ask entrypoint."""

from __future__ import annotations

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

from ._ask_0 import (
    _FRIENDLY,
    _context_lookup,
    _friendly_error,
    _has_ask_permission,
    _sse,
)
from ._ask_1 import _build_frozen_request_context, _resolve_context_and_data
from ._ask_2 import _events_from_outcome
from ._ask_3 import _call_stream, _invoke

try:
    from finsight.composition.ask_question import get_ask_use_case as _get_ask_use_case_raw
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
