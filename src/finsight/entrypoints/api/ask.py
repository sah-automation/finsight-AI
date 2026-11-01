# ruff: noqa: BLE001, PLC0415, PLR0911, PLR0912, PLR0915, PLR2004, S110, I001, F403, F405
from __future__ import annotations

from typing import Any, TYPE_CHECKING
from fastapi import Body

from ._ask_0 import *
from ._ask_1 import *
from ._ask_2 import *
from ._ask_3 import *
from ._ask_4 import *

if TYPE_CHECKING:
    from fastapi.responses import StreamingResponse


class Ask:
    """Thin wrapper exposing the ask entrypoint as a callable object."""

    def __init__(self, use_case: Any = None, context: Any = None) -> None:
        self.use_case = use_case
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
