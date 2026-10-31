# ruff: noqa: BLE001, PLC0415, PLR0911, PLR0912, PLR0913, PLR0915, PLR0917, PLR2004, RET504, SIM102, SIM110, TRY201, TRY300, TRY301, E501, S110, S112, N815, B004, B007, B023, B025, B904, PGH004, E402, F404, I001, ANN401, F403, F405, F821
from __future__ import annotations
from ._ask_0 import *
from ._ask_1 import *
from ._ask_2 import *
from ._ask_3 import *
from ._ask_4 import *

for _r in (router, router_qa, router_question, router_questions):

    @_r.get('/health')
    async def _health() -> dict[str, str]:
        return {'status': 'ok'}

    @_r.post(
        '',
        response_model=None,
        responses={
            200: {
                'description': 'Server-sent event stream of typed question events.',
                'content': {
                    'text/event-stream': {
                        'schema': {'$ref': '#/components/schemas/AskQuestionEvent'}
                    }
                },
            }
        },
    )
    async def _post(
        payload: _AskQuestionRequest | None = Body(default=None), context: Any = None
    ) -> StreamingResponse:
        data = (
            payload.model_dump(exclude_none=True)
            if isinstance(payload, _AskQuestionRequest)
            else payload
        )
        return await _handle(data, context=context)

    @_r.post(
        '/',
        response_model=None,
        responses={
            200: {
                'description': 'Server-sent event stream of typed question events.',
                'content': {
                    'text/event-stream': {
                        'schema': {'$ref': '#/components/schemas/AskQuestionEvent'}
                    }
                },
            }
        },
    )
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

import sys as _inj_sys

_all_helper_names = [
    'APIRouter',
    'Any',
    'AskQuestionEvent',
    'AskQuestionRequest',
    'AuthorizationError',
    'BaseModel',
    'Body',
    'ConfigDict',
    'EXTRA_ROUTERS',
    'Field',
    'HTTPException',
    'Role',
    'StreamingResponse',
    'ValidationError',
    '_Any',
    '_AskQuestionEvent',
    '_AskQuestionRequest',
    '_BadRequestError',
    '_CONTEXT_KEYS',
    '_EVENT_ALIASES',
    '_FRIENDLY',
    '_ForbiddenError',
    '_PAYLOAD_KEYS',
    '_REPOSITORY_KEYS',
    '_ServerError',
    '_USE_CASE_KEYS',
    '_await',
    '_call_stream',
    '_collect_iterable',
    '_context_lookup',
    '_events_from_outcome',
    '_flatten',
    '_friendly_error',
    '_get',
    '_get_ask_use_case',
    '_handle',
    '_has_ask_permission',
    '_http_ask',
    '_is_context',
    '_is_use_case',
    '_normalize_event',
    '_resolve_context_and_data',
    '_resolve_use_case',
    '_sse',
    '_wrap_sync_callable',
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
for _ci in range(5):
    _mod = _inj_sys.modules.get('finsight.entrypoints.api.' + '_ask' + '_' + str(_ci))
    if _mod is not None:
        for _n in _all_helper_names:
            if _n not in _mod.__dict__:
                for _ci2 in range(5):
                    _mod2 = _inj_sys.modules.get(
                        'finsight.entrypoints.api.' + '_ask' + '_' + str(_ci2)
                    )
                    if _mod2 is not None and _n in _mod2.__dict__:
                        _mod.__dict__[_n] = _mod2.__dict__[_n]
                        break
