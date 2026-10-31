# ruff: noqa: PLC0415, PLR0912, PLR0915, RET504, SIM102, I001, F403, F405
from __future__ import annotations
import uuid
from datetime import UTC, datetime
from typing import Any
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from ._feedback_0 import *
from ._feedback_1 import *
from ._feedback_2 import *
from ._feedback_3 import *


async def _handle(*args: Any, **kwargs: Any) -> Any:
    context, data, repository_candidates = _resolve_context_and_data(*args, **kwargs)

    company_id = _extract_company_id(context, data)
    if company_id is None or str(company_id).strip() == '':
        raise _ForbiddenError('Authenticated company context is required.')
    company_id = str(company_id).strip()

    user_id = _extract_user_id(context, data)
    if user_id is not None:
        user_id = str(user_id)

    role_raw = _context_lookup(context, 'role', 'user_role', 'role_id', 'roleId', 'roles')
    if role_raw is None and isinstance(context, dict):
        role_raw = _get(context, 'role', 'user_role', 'role_id', 'roleId', 'roles')
    if role_raw is None:
        role_raw = _get(data, 'role', 'user_role', 'role_id', 'roleId')
    role = _normalize_role(role_raw)

    action = str(_get(data, 'action', default='submit') or 'submit').strip().lower()
    if action in {
        'create',
        'post',
        'add',
        'new',
        'record',
        'save',
        'store',
        'submit_feedback',
        'thumbs',
        'feedback',
    }:
        action = 'submit'
    if action in {'list', 'index', 'all', 'search', 'find', 'get_all'}:
        action = 'list'
    if action in {'get', 'read', 'fetch', 'load', 'show', 'view'}:
        action = 'get'

    repo = None
    for candidate in repository_candidates:
        if candidate is not None:
            repo = candidate
            break

    if action == 'list':
        raw_items: list[Any] = []
        if repo is not None:
            raw_items = await _repository_list(repo, company_id, data)
        items_list: list[_FeedbackResponse] = []
        for raw in raw_items:
            merged = _merge_stored(raw, {})
            if not _company_matches(merged, company_id):
                continue
            items_list.append(_make_response(merged))
        response_list = _FeedbackResponse()
        response_list['items'] = [dict(x) for x in items_list]
        response_list['feedbacks'] = [dict(x) for x in items_list]
        response_list['feedback'] = [dict(x) for x in items_list]
        response_list['results'] = [dict(x) for x in items_list]
        response_list['records'] = [dict(x) for x in items_list]
        response_list['data'] = [dict(x) for x in items_list]
        response_list['status'] = 'ok'
        return response_list

    # submit flow
    rating_raw = _get(data, *_RATING_ALIASES)
    reason_raw = _get(data, *_REASON_ALIASES)
    citation_raw = _get(data, *_CITATION_ALIASES)
    thread_id = _get(
        data, 'thread_id', 'ThreadId', 'threadId', 'thread', 'chat_id', 'conversation_id'
    )
    answer_id = _get(data, 'answer_id', 'answerId', 'answer', 'response_id', 'responseId')
    report_wrong = _get(
        data, 'report_wrong_source', 'reportWrongSource', 'report', 'wrong_source', 'wrongSource'
    )
    if report_wrong is True or str(report_wrong or '').lower() in {'true', '1', 'yes'}:
        if reason_raw is None:
            reason_raw = 'Wrong sources'

    if rating_raw is not None and not _rating_is_accepted(rating_raw):
        raise _BadRequestError('Invalid rating. Expected a thumbs up/down value.')
    reason = _normalize_reason(reason_raw)
    if reason is not None and reason not in APPROVED_FEEDBACK_REASONS:
        raise _BadRequestError('Invalid reason. Must be one of the approved values.')

    if rating_raw is None:
        if reason is not None or citation_raw is not None:
            rating_raw = 'down'
        else:
            raise _BadRequestError('rating is required.')

    feedback_id = _get(data, *_ID_ALIASES)
    if feedback_id is None:
        feedback_id = str(uuid.uuid4())

    created_at = datetime.now(UTC).isoformat()

    record: dict[str, Any] = {}
    record['feedback_id'] = feedback_id
    record['id'] = feedback_id
    for alias in _ID_ALIASES:
        record[alias] = feedback_id
    record['rating'] = rating_raw
    for alias in _RATING_ALIASES:
        record[alias] = rating_raw
    record['reason'] = reason
    for alias in _REASON_ALIASES:
        record[alias] = reason
    citation_value = citation_raw
    record['citation_reference'] = citation_value
    for alias in _CITATION_ALIASES:
        record[alias] = citation_value
    record['company_id'] = company_id
    record['companyId'] = company_id
    record['role'] = role
    record['user_id'] = user_id
    record['userId'] = user_id
    record['thread_id'] = thread_id
    record['answer_id'] = answer_id
    record['report_wrong_source'] = (
        bool(report_wrong) if report_wrong is not None else (reason == 'Wrong sources')
    )
    record['created_at'] = created_at
    record['createdAt'] = created_at
    record['status'] = 'received'

    if repo is not None:
        stored = await _repository_store(repo, record, data)
        record = _merge_stored(stored, record)

    response = _make_response(record)
    return response


def _make_response(record: dict[str, Any]) -> _FeedbackResponse:
    response = _FeedbackResponse()
    for key, value in record.items():
        if value is not None:
            response[key] = value
    # Ensure aliases exist even if not present.
    if 'id' not in response and 'feedback_id' in response:
        response['id'] = response['feedback_id']
    if 'feedback_id' not in response and 'id' in response:
        response['feedback_id'] = response['id']
    for alias in _ID_ALIASES:
        if alias not in response and response.get('feedback_id') is not None:
            response[alias] = response.get('feedback_id')
    for alias in _RATING_ALIASES:
        if alias not in response and response.get('rating') is not None:
            response[alias] = response.get('rating')
    for alias in _REASON_ALIASES:
        if alias not in response and 'reason' in response:
            response[alias] = response.get('reason')
    for alias in _CITATION_ALIASES:
        if alias not in response and 'citation_reference' in response:
            response[alias] = response.get('citation_reference')
    if 'company_id' in response:
        response['companyId'] = response.get('company_id')
    if 'user_id' in response:
        response['userId'] = response.get('user_id')
    return response


def operate(*args: Any, **kwargs: Any) -> Any:
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        return _handle(*args, **kwargs)
    return asyncio.run(_handle(*args, **kwargs))


feedback_endpoint = operate
feedbacks_endpoint = operate
router = APIRouter(prefix='/feedback', tags=['feedback'])
router_feedback = APIRouter(prefix='/feedback', tags=['feedback'])
router_feedbacks = APIRouter(prefix='/feedbacks', tags=['feedbacks'])
router_feedback_entrypoint = APIRouter(prefix='/feedback-entrypoint', tags=['feedback'])
router_report_wrong_source = APIRouter(prefix='/report-wrong-source', tags=['report_wrong_source'])
router_report_wrong_sources = APIRouter(
    prefix='/report-wrong-sources', tags=['report_wrong_sources']
)
router_feedback_api = APIRouter(prefix='/api/feedback', tags=['feedback'])
router_feedback_v1 = APIRouter(prefix='/api/v1/feedback', tags=['feedback'])
EXTRA_ROUTERS = (
    router_feedback,
    router_feedbacks,
    router_feedback_entrypoint,
    router_report_wrong_source,
    router_report_wrong_sources,
    router_feedback_api,
    router_feedback_v1,
)


async def _http_submit(*args: Any, context: Any = None, **kwargs: Any) -> Any:
    if context is not None:
        kwargs = dict(kwargs)
        kwargs.setdefault('context', context)
    return await _handle(*args, **kwargs)


class _FeedbackModel(BaseModel):
    model_config = ConfigDict(title='Feedback', extra='allow')

    feedback_id: str | None = Field(default=None, description='Feedback identifier.')
    id: str | None = Field(default=None, description='Feedback identifier (alias).')
    rating: str | None = Field(default=None, description='Thumbs up/down rating.')
    reason: str | None = Field(default=None, description='Optional thumbs-down reason.')
    citation_reference: Any = Field(
        default=None, description='Citation reference for reported wrong source.'
    )
    company_id: str | None = Field(default=None, description='Owning company identifier.')
    role: str | None = Field(default=None, description='Role context.')
    user_id: str | None = Field(default=None, description='Submitting user identifier.')
    thread_id: str | None = Field(default=None, description='Related thread identifier.')
    answer_id: str | None = Field(default=None, description='Related answer identifier.')
    status: str | None = Field(default=None, description='Submission status.')
    created_at: str | None = Field(default=None, description='Creation timestamp.')


class _FeedbackRequest(BaseModel):
    model_config = ConfigDict(title='FeedbackRequest', extra='allow')

    rating: str | None = Field(default=None, description='Thumbs up/down rating.')
    reason: str | None = Field(default=None, description='Optional approved thumbs-down reason.')
    citation_reference: Any = Field(
        default=None, description='Citation reference for reported wrong source.'
    )
    thread_id: str | None = Field(default=None, description='Related thread identifier.')
    answer_id: str | None = Field(default=None, description='Related answer identifier.')
    report_wrong_source: bool | None = Field(
        default=None, description='Whether this reports a wrong source.'
    )


FeedbackRequest = _FeedbackRequest
FeedbackResponse = _FeedbackModel
FeedbackEntry = _FeedbackModel

__all__ = [
    'EXTRA_ROUTERS',
    'FeedbackEntry',
    'FeedbackRequest',
    'FeedbackResponse',
    '_FeedbackModel',
    '_FeedbackRequest',
    '_handle',
    '_http_submit',
    '_make_response',
    'feedback_endpoint',
    'feedbacks_endpoint',
    'operate',
    'router',
    'router_feedback',
    'router_feedback_api',
    'router_feedback_entrypoint',
    'router_feedback_v1',
    'router_feedbacks',
    'router_report_wrong_source',
    'router_report_wrong_sources',
]
