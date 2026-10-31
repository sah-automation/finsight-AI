# ruff: noqa: BLE001, PLR0912, PLR0915, TRY301, N815, I001, F403, F405
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
from ._ask_3 import *


async def _handle(*args: Any, **kwargs: Any) -> StreamingResponse:
    context, data, use_case_candidate, role_candidate = await _resolve_context_and_data(
        *args, **kwargs
    )

    async def _generator() -> Any:
        emitted_complete = False
        try:
            # Permission best-effort.
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
            # company_id may be embedded in context.
            if company_id is None and context is not None:
                company_id = _context_lookup(
                    context,
                    'company_id',
                    'companyId',
                    'company',
                    'tenant_id',
                    'tenantId',
                    'tenant',
                )
            if company_id is not None:
                data['company_id'] = company_id
            else:
                yield _sse(
                    'error',
                    {'message': 'company_id is required.', 'code': 'ValidationError'},
                )
                yield _sse('complete', {'done': True, 'error': True})
                return

            question = data.get('question') or data.get('query')
            if not question:
                # Maybe passed as positional raw.
                question = data.get('_raw')
                if question is not None:
                    question = str(question)
                    data['question'] = question

            # Input status.
            yield _sse('status', {'status': 'received', 'question': question})

            use_case = await _resolve_use_case(use_case_candidate, data, context)

            # Try streaming first.
            stream_obj = await _call_stream(use_case, data, context)
            agen = await _collect_iterable(stream_obj) if stream_obj is not None else None

            if agen is not None:
                yield _sse('status', {'status': 'answering'})
                async for raw in agen:
                    normalized = _normalize_event(raw)
                    if normalized is None:
                        continue
                    etype, payload = normalized
                    # Map alias types.
                    canonical = _EVENT_ALIASES.get(str(etype).lower().replace('-', '_'), str(etype))
                    if canonical in ('complete',):
                        emitted_complete = True
                    yield _sse(canonical, payload)
                if not emitted_complete:
                    yield _sse('complete', {'done': True})
                return

            # Non-streaming path.
            method = None
            for name in ('execute', 'run', 'ask', 'answer', 'handle'):
                candidate_method = getattr(use_case, name, None)
                if callable(candidate_method):
                    method = candidate_method
                    break
            if method is None:
                raise RuntimeError('ask use case is not callable')

            def _invoke(kwargs_with: dict[str, Any]) -> Any:
                for args_tuple in ((data,), (data, context), (context, data)):
                    try:
                        return method(*args_tuple)
                    except TypeError:
                        continue
                try:
                    return method(**kwargs_with)
                except TypeError:
                    pass
                return method()

            outcome_raw = None
            try:
                outcome_raw = _invoke(
                    {
                        'question': data.get('question'),
                        'context': context,
                        'company_id': data.get('company_id'),
                        'thread_id': data.get('thread_id'),
                    }
                )
            except TypeError:
                try:
                    outcome_raw = method()
                except Exception:
                    outcome_raw = None
            outcome = outcome_raw
            if inspect.isawaitable(outcome):
                outcome = await outcome

            for etype, payload in _events_from_outcome(outcome, data):
                if etype == 'complete':
                    emitted_complete = True
                yield _sse(etype, payload)

            if not emitted_complete:
                yield _sse('complete', {'done': True})
        except _InsufficientDataError as exc:
            reason = getattr(exc, 'reason', None) or _friendly_error(exc)
            yield _sse('insufficient_data', {'reason': reason, 'question': data.get('question')})
            yield _sse('complete', {'done': True, 'insufficient_data': True})
        except ValidationError as exc:
            msg = getattr(exc, 'message', None) or to_user_message(exc) or _FRIENDLY['config']
            yield _sse('error', {'message': msg, 'code': 'ValidationError'})
            yield _sse('complete', {'done': True, 'error': True})
        except AuthorizationError as exc:
            msg = (
                getattr(exc, 'message', None)
                or to_user_message(exc)
                or 'You do not have permission to perform this action.'
            )
            yield _sse('error', {'message': msg, 'code': 'AuthorizationError'})
            yield _sse('complete', {'done': True, 'error': True})
        except Exception as exc:
            # Never leak raw errors or document text.
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


class _AskQuestionRequest(BaseModel):
    """Typed request model for ask endpoints."""

    model_config = ConfigDict(title='AskQuestionRequest')

    question: str | None = None
    query: str | None = None
    q: str | None = None
    company_id: str | None = None
    companyId: str | None = None
    thread_id: str | None = None
    threadId: str | None = None
    access_scope: Any = None
    context: Any = None
    use_case: Any = None


AskQuestionRequest = _AskQuestionRequest


class _AskQuestionEvent(BaseModel):
    """Representative typed SSE question event."""

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
