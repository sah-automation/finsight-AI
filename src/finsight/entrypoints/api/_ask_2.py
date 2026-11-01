# ruff: noqa: PLR0912, PLR0915
"""Outcome to event normalization helpers for the ask entrypoint."""

from __future__ import annotations

from typing import Any

from ._ask_0 import _get


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
