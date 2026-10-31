# ruff: noqa: PLR0912, SIM102, B007, I001, ANN401, F403, F405
from __future__ import annotations
import inspect
from typing import Any
from ._feedback_0 import *


def _normalize_reason(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if text == '':
            return None
        return text
    return str(value).strip()


def _rating_is_accepted(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return str(value).strip() in {'1', '-1'}
    text = str(value).strip().lower().replace(' ', '_').replace('-', '_')
    if text == '':
        return True
    return text in {item.lower().replace(' ', '_').replace('-', '_') for item in _RATING_ACCEPTED}


def _resolve_context_and_data(*args: Any, **kwargs: Any) -> tuple[Any, dict[str, Any], list[Any]]:
    working = dict(kwargs)
    context = None
    for key in list(working):
        key_l = key.lower()
        if key_l in _CONTEXT_KEYS:
            value = working.pop(key)
            if context is None:
                context = value
            else:
                working.update(_flatten(value))
    for value in args:
        if context is None and _is_context(value):
            context = value
        elif isinstance(value, dict):
            working.update(value)
        else:
            flattened = _flatten(value)
            if flattened:
                working.update(flattened)
    if context is None:
        for value in args:
            if isinstance(value, dict) and _is_context(value):
                context = value
                break
    if context is None:
        for key, value in working.items():
            if isinstance(value, dict) and _is_context(value):
                context = value
                break
    data = dict(working)
    for key in ('request', 'payload', 'body', 'data', 'command', 'input', 'feedback'):
        if key in data and isinstance(data.get(key), dict):
            nested = data.pop(key)
            data.update(nested)
    for ctx_key in _CONTEXT_KEYS:
        if ctx_key in data and context is None:
            context = data.pop(ctx_key)
    canonical = dict(data)
    canonical.update(_flatten(canonical))
    data = canonical
    # action default
    action = _get(data, 'action', 'operation', 'mode', 'kind', 'verb')
    if action is None:
        if any(k in data for k in ('list', 'index', 'all', 'search', 'find', 'get_feedbacks')):
            action = 'list'
        elif any(k in data for k in ('get', 'read', 'fetch', 'load')) and _get(
            data, 'feedback_id', 'id'
        ):
            action = 'get'
        else:
            action = 'submit'
    data['action'] = str(action).strip().lower()
    return context, data, _find_repository_candidates(args, kwargs, context)


def _find_repository_candidates(
    args: tuple[Any, ...], kwargs: dict[str, Any], context: Any
) -> list[Any]:
    candidates: list[Any] = []
    for key, value in kwargs.items():
        lowered = key.lower()
        if any(
            token in lowered
            for token in (
                'feedback',
                'rating',
                'review',
                'store',
                'repo',
                'repository',
                'provider',
                'client',
                'adapter',
                'history',
                'use_case',
                'service',
                'handler',
                'orchestrator',
            )
        ):
            if value is not None and value not in candidates:
                candidates.append(value)
    if context is not None:
        for name in (
            'feedback_repository',
            'feedback_repo',
            'feedback_store',
            'feedback_history',
            'feedbacks',
            'feedbacks_repository',
            'review_repository',
            'repository',
            'repo',
            'store',
            'provider',
            'client',
            'adapter',
            'use_case',
            'service',
            'handler',
            'orchestrator',
        ):
            value = _context_lookup(context, name)
            if value is not None and value not in candidates:
                candidates.append(value)
    for value in args:
        if value is None:
            continue
        if isinstance(value, (list, tuple, dict)):
            continue
        if any(
            hasattr(value, attr)
            for attr in (
                'save_feedback',
                'store_feedback',
                'create_feedback',
                'submit_feedback',
                'record_feedback',
                'report_wrong_source',
                'save',
                'store',
                'create',
                'add',
                'insert',
                'put',
                'write',
                'append',
                'record',
                'submit',
                'report',
                'persist',
                'list',
                'get',
                'execute',
                'run',
                'handle',
                'invoke',
                'call',
                '__call__',
            )
        ):
            if value not in candidates:
                candidates.append(value)
    return candidates


async def _await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


class _FeedbackResponse(dict[str, Any]):
    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value

    def model_dump(self) -> dict[str, Any]:
        return dict(self)

    def dict(self) -> dict[str, Any]:
        return dict(self)


def _set_aliases(record: dict[str, Any], field_aliases: tuple[str, ...], value: Any) -> None:
    for alias in field_aliases:
        record[alias] = value


__all__ = [
    '_FeedbackResponse',
    '_await',
    '_find_repository_candidates',
    '_normalize_reason',
    '_rating_is_accepted',
    '_resolve_context_and_data',
    '_set_aliases',
]
