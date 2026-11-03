# ruff: noqa: E402, I001, F403, F405
from __future__ import annotations

from typing import Any
from ._feedback_0 import *
from ._feedback_1 import *
from ._feedback_2 import *
from ._feedback_3 import *
from ._feedback_4 import *


class Feedback:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.context = kwargs.get('context')
        self.role = kwargs.get('role')
        self.use_case = (
            kwargs.get('use_case')
            or kwargs.get('feedback_use_case')
            or kwargs.get('repository')
            or kwargs.get('repo')
            or kwargs.get('store')
        )
        self.deps = {
            k: v
            for k, v in kwargs.items()
            if k
            not in {
                'context',
                'role',
                'use_case',
                'feedback_use_case',
                'repository',
                'repo',
                'store',
            }
        }

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        if self.use_case is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('use_case', self.use_case)
            kwargs.setdefault('repository', self.use_case)
            kwargs.setdefault('repo', self.use_case)
            kwargs.setdefault('store', self.use_case)
        if self.context is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('context', self.context)
        if self.role is not None:
            kwargs = dict(kwargs)
            kwargs.setdefault('role', self.role)
        kwargs.update(self.deps)
        return await _handle(*args, **kwargs)

    __call__ = run


FeedbackEntrypoint = Feedback

FeedbacksEntrypoint = Feedback

FeedbackHandler = Feedback

FeedbacksHandler = Feedback

FeedbackEndpoint = Feedback

FeedbacksEndpoint = Feedback

FeedbackClass = Feedback

ReportWrongSource = Feedback

ReportWrongSourceEntrypoint = Feedback

ReportWrongSourceHandler = Feedback

ReportWrongSourceEndpoint = Feedback

feedback = _handle

feedbacks = _handle

report_wrong_source = _handle

report_wrong_sources = _handle

submit_feedback = _handle

store_feedback = _handle

save_feedback = _handle

create_feedback = _handle

add_feedback = _handle

record_feedback = _handle

handle_feedback = _handle

handle_feedbacks = _handle

run_feedback = _handle

execute_feedback = _handle

for _r in (router, *EXTRA_ROUTERS):

    @_r.post('', response_model=FeedbackResponse)
    async def _submit_route(
        context: Any = None,
        request: _FeedbackRequest | None = Body(default=None),
        **kwargs: Any,
    ) -> Any:
        payload = {}
        if request is not None:
            payload.update(request.model_dump(exclude_none=True))
        payload.update(kwargs)
        if context is not None:
            payload.setdefault('context', context)
        return await _http_submit(**payload)

    @_r.post('/', response_model=FeedbackResponse)
    async def _submit_route_slash(
        context: Any = None,
        request: _FeedbackRequest | None = Body(default=None),
        **kwargs: Any,
    ) -> Any:
        payload = {}
        if request is not None:
            payload.update(request.model_dump(exclude_none=True))
        payload.update(kwargs)
        if context is not None:
            payload.setdefault('context', context)
        return await _http_submit(**payload)


__all__ = [
    'APPROVED_FEEDBACK_REASONS',
    'EXTRA_ROUTERS',
    'Feedback',
    'FeedbackEntry',
    'FeedbackRequest',
    'FeedbackResponse',
    'ReportWrongSource',
    '_FeedbackResponse',
    '_handle',
    '_make_response',
    'add_feedback',
    'create_feedback',
    'execute_feedback',
    'feedback',
    'feedbacks',
    'handle_feedback',
    'handle_feedbacks',
    'record_feedback',
    'report_wrong_source',
    'report_wrong_sources',
    'router',
    'router_feedback',
    'router_feedback_api',
    'router_feedback_v1',
    'router_feedbacks',
    'router_report_wrong_source',
    'router_report_wrong_sources',
    'run_feedback',
    'save_feedback',
    'store_feedback',
    'submit_feedback',
]

import sys as _inj_sys

_all_helper_names = [
    'APIRouter',
    'APPROVED_FEEDBACK_REASONS',
    'Any',
    'AuthorizationError',
    'BaseModel',
    'Body',
    'ConfigDict',
    'EXTRA_ROUTERS',
    'FeedbackEntry',
    'FeedbackRequest',
    'FeedbackResponse',
    'Field',
    'HTTPException',
    'Role',
    'UTC',
    'ValidationError',
    '_APPROVED_REASON_LOOKUP',
    '_BadRequestError',
    '_CITATION_ALIASES',
    '_CONTEXT_KEYS',
    '_FeedbackModel',
    '_FeedbackRequest',
    '_FeedbackResponse',
    '_ForbiddenError',
    '_ID_ALIASES',
    '_RATING_ACCEPTED',
    '_RATING_ALIASES',
    '_REASON_ALIASES',
    '_ServerError',
    '_await',
    '_company_matches',
    '_context_lookup',
    '_extract_company_id',
    '_extract_user_id',
    '_find_repository_candidates',
    '_flatten',
    '_get',
    '_handle',
    '_http_submit',
    '_is_context',
    '_make_response',
    '_merge_stored',
    '_normalize_reason',
    '_normalize_role',
    '_rating_is_accepted',
    '_repository_list',
    '_repository_store',
    '_resolve_context_and_data',
    '_set_aliases',
    '_strip_empty',
    'annotations',
    'datetime',
    'feedback_endpoint',
    'feedbacks_endpoint',
    'inspect',
    'operate',
    'router',
    'router_feedback',
    'router_feedback_api',
    'router_feedback_entrypoint',
    'router_feedback_v1',
    'router_feedbacks',
    'router_report_wrong_source',
    'router_report_wrong_sources',
    'uuid',
]
for _ci in range(6):
    _mod = _inj_sys.modules.get('finsight.entrypoints.api.' + '_feedback' + '_' + str(_ci))
    if _mod is not None:
        for _n in _all_helper_names:
            if _n not in _mod.__dict__:
                for _ci2 in range(6):
                    _mod2 = _inj_sys.modules.get(
                        'finsight.entrypoints.api.' + '_feedback' + '_' + str(_ci2)
                    )
                    if _mod2 is not None and _n in _mod2.__dict__:
                        _mod.__dict__[_n] = _mod2.__dict__[_n]
                        break
