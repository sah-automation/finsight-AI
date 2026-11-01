"""Composition helpers for the ask-question use case."""

from __future__ import annotations

from typing import Any


def get_ask_use_case(*args: Any, **kwargs: Any) -> Any:
    return _get_ask_use_case_impl(*args, **kwargs)


def _get_ask_use_case_impl(*args: Any, **kwargs: Any) -> Any:
    """Return the wired ask-question use case."""
    provided = (
        kwargs.get('ask_question_use_case') or kwargs.get('ask_use_case') or kwargs.get('use_case')
    )
    if provided is not None:
        return provided

    from .container import get_default_container, resolve_config

    config = resolve_config(*args, **kwargs)
    if config is None:
        config = kwargs.get('config')

    # Reuse an already-wired container use case when possible.
    container = None
    for key in ('container', 'composition', 'root', 'app', 'context'):
        candidate = kwargs.get(key)
        if candidate is not None:
            container = candidate
            break
    if container is None and not args and not kwargs:
        container = get_default_container()
    if container is not None:
        for attr in (
            'ask_question_use_case',
            'ask_use_case',
            'ask_question',
            'ask',
            'qa_use_case',
            'question_use_case',
        ):
            value = getattr(container, attr, None)
            if value is not None:
                return value

    # Use the composition root wiring (no session parameter).
    from .container import build_container

    built = build_container(*args, **kwargs)
    for attr in (
        'ask_question_use_case',
        'ask_use_case',
        'ask_question',
        'ask',
        'qa_use_case',
        'question_use_case',
    ):
        value = getattr(built, attr, None)
        if value is not None:
            return value

    # If a container-less path is taken but no use case resolved, fall back to
    # the default container instead of probing ports manually.
    container = get_default_container()
    if container is not None:
        for attr in (
            'ask_question_use_case',
            'ask_use_case',
            'ask_question',
            'ask',
            'qa_use_case',
            'question_use_case',
        ):
            value = getattr(container, attr, None)
            if value is not None:
                return value

    raise RuntimeError('ask use case could not be resolved from the composition root')


def build_ask_question(*args: Any, **kwargs: Any) -> Any:
    return get_ask_use_case(*args, **kwargs)


def build_ask_use_case(*args: Any, **kwargs: Any) -> Any:
    return get_ask_use_case(*args, **kwargs)


def build_ask_question_use_case(*args: Any, **kwargs: Any) -> Any:
    return get_ask_use_case(*args, **kwargs)


def resolve_ask_use_case(*args: Any, **kwargs: Any) -> Any:
    return get_ask_use_case(*args, **kwargs)


__all__ = [
    'build_ask_question',
    'build_ask_question_use_case',
    'build_ask_use_case',
    'get_ask_use_case',
    'resolve_ask_use_case',
]
