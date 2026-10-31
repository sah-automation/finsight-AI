# ruff: noqa: BLE001, PLR0912, PLR0915, SIM102, S110, I001, F403, F405
from __future__ import annotations
import inspect
from typing import Any
from ._threads_0 import *


def _find_repository_candidates(
    args: tuple[Any, ...], kwargs: dict[str, Any], context: Any
) -> list[Any]:
    candidates: list[Any] = []
    for key, value in kwargs.items():
        lowered = key.lower()
        if any(
            token in lowered
            for token in ('repo', 'repository', 'history', 'store', 'provider', 'client', 'adapter')
        ):
            if value is not None and value not in candidates:
                candidates.append(value)
    if context is not None:
        for name in (
            'thread_repository',
            'threads_repository',
            'chat_thread_repository',
            'chat_threads_repository',
            'chat_repository',
            'chat_history',
            'thread_history',
            'thread_store',
            'threads',
            'conversation_repository',
            'conversations',
            'history',
            'repository',
            'repo',
            'chat_history_repository',
        ):
            value = _context_lookup(context, name)
            if value is not None and value not in candidates:
                candidates.append(value)
    for value in args:
        if isinstance(value, (list, tuple, dict)):
            continue
        if any(
            hasattr(value, attr)
            for attr in (
                'list_threads',
                'get_thread',
                'list',
                'get',
                'fetch',
                'read',
                'find',
                'search',
            )
        ):
            if value not in candidates:
                candidates.append(value)
    return candidates


def _normalize_thread_id(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, dict):
        value = _get(value, 'thread_id', 'threadId', 'id', 'thread', 'chat_id', 'conversation_id')
    if value is None:
        return ''
    return str(value).strip()


def _item_to_dict(item: Any) -> _ThreadResponse:
    response = _ThreadResponse()
    if isinstance(item, dict):
        response.update(item)
    elif hasattr(item, 'model_dump'):
        try:
            data = item.model_dump()
            if isinstance(data, dict):
                response.update(data)
        except Exception:
            pass
    elif hasattr(item, 'dict'):
        try:
            data = item.dict()
            if isinstance(data, dict):
                response.update(data)
        except Exception:
            pass
    else:
        for attr in (
            'thread_id',
            'threadId',
            'thread',
            'id',
            'chat_id',
            'conversation_id',
            'company_id',
            'companyId',
            'company',
            'user_id',
            'userId',
            'uid',
            'title',
            'name',
            'subject',
            'question',
            'query',
            'text',
            'prompt',
            'answer',
            'answer_id',
            'answerId',
            'response',
            'created_at',
            'createdAt',
            'updated_at',
            'updatedAt',
            'messages',
            'answers',
            'citations',
            'model',
            'status',
            'access_scope',
            'role',
        ):
            value = getattr(item, attr, None)
            if value is not None:
                response[attr] = value

    # Canonical aliases.
    tid = response.get('thread_id')
    if tid is None:
        tid = response.get('threadId')
    if tid is None:
        tid = response.get('thread')
    if tid is None:
        tid = response.get('id')
    if tid is None:
        tid = response.get('chat_id')
    if tid is None:
        tid = response.get('conversation_id')
    if tid is not None:
        response['thread_id'] = tid
    cid = response.get('company_id')
    if cid is None:
        cid = response.get('companyId')
    if cid is None:
        cid = response.get('company')
    if cid is not None:
        response['company_id'] = cid
    uid = response.get('user_id')
    if uid is None:
        uid = response.get('userId')
    if uid is None:
        uid = response.get('uid')
    if uid is not None:
        response['user_id'] = uid
    q = response.get('question')
    if q is None:
        q = response.get('query')
    if q is None:
        q = response.get('text')
    if q is None:
        q = response.get('prompt')
    if q is not None:
        response['question'] = q
    if response.get('answer') is None and response.get('response') is not None:
        response['answer'] = response.get('response')
    if response.get('created_at') is None and response.get('createdAt') is not None:
        response['created_at'] = response.get('createdAt')
    if response.get('updated_at') is None and response.get('updatedAt') is not None:
        response['updated_at'] = response.get('updatedAt')
    if response.get('title') is None and response.get('name') is not None:
        response['title'] = response.get('name')
    if response.get('thread_id') is None and response.get('_id') is not None:
        response['thread_id'] = response.get('_id')
    if 'status' not in response:
        response['status'] = 'ok'
    return response


def _company_matches(item: _ThreadResponse, company_id: Any) -> bool:
    item_company = item.get('company_id')
    if item_company is None:
        return True
    return str(item_company).strip() == str(company_id).strip()


def _strip_empty(mapping: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if value is not None}


async def _await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


__all__ = [
    '_await',
    '_company_matches',
    '_find_repository_candidates',
    '_item_to_dict',
    '_normalize_thread_id',
    '_strip_empty',
]
