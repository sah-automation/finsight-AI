# ruff: noqa: F401, N801, N818, E501, SIM110, PLR1714, RUF100
# ruff: noqa: BLE001, PLC0415, PLR0911, PLR0912, PLR0915, PLR2004, S110, I001, F403, F405, E402, F811
# ruff: noqa: BLE001, E501, S110, PLR0911
"""Shared helpers for the ask entrypoint."""

from __future__ import annotations

from ._shared import (
    _build_frozen_request_context,
    _call_stream,
    _events_from_outcome,
    _friendly_error,
    _has_ask_permission,
    _invoke,
    _resolve_context_and_data,
    _sse,
)

from ._shared import (
    _BadRequestError,
    _ForbiddenError,
    _ServerError,
    _await,
    _context_lookup,
    _flatten,
    _get,
    _is_context,
    _is_use_case,
)

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


_CONTEXT_KEYS = ('request_context', 'context', 'ctx')
_USE_CASE_KEYS = ('use_case', 'ask_use_case', 'qa_use_case', 'service', 'orchestrator', 'handler')
_PAYLOAD_KEYS = ('request', 'payload', 'body', 'data', 'command', 'input', 'query')


_FRIENDLY = {
    'busy': 'The system is busy right now. Please try again in a moment.',
    'config': 'This question could not be processed due to a configuration issue. Please contact support.',
    'provider': 'The answer service is temporarily unavailable. Please try again shortly.',
    'insufficient': 'I do not have enough data to answer that question reliably.',
    'generic': 'Unable to answer this question right now. Please try again.',
}


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


__all__ = ['_build_frozen_request_context', '_resolve_context_and_data']


# ruff: noqa: PLR0912, PLR0915
"""Outcome to event normalization helpers for the ask entrypoint."""


from typing import Any


__all__ = ['_events_from_outcome']


"""Call helpers for the ask use case."""


import inspect
from typing import Any


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
